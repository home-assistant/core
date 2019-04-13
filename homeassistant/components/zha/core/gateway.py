"""
Virtual gateway for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import asyncio
import collections
import itertools
import logging
import os
import traceback

from homeassistant.components.system_log import LogEntry, _figure_out_source
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_component import EntityComponent

from ..api import async_get_device_info
from .channels import MAINS_POWERED, ZDOChannel
from .const import (
    ADD_DEVICE_RELAY_LOGGERS, ATTR_MANUFACTURER, BELLOWS, CONF_BAUDRATE,
    CONF_DATABASE, CONF_RADIO_TYPE, CONF_USB_PATH, CONTROLLER, CURRENT,
    DATA_ZHA, DATA_ZHA_BRIDGE_ID, DATA_ZHA_CORE_COMPONENT, DATA_ZHA_GATEWAY,
    DEBUG_LEVELS, DEFAULT_BAUDRATE, DEFAULT_DATABASE_NAME, DEVICE_FULL_INIT,
    DEVICE_INFO, DEVICE_JOINED, DEVICE_REMOVED, DOMAIN, IEEE, LOG_ENTRY,
    LOG_OUTPUT, MODEL, NWK, ORIGINAL, RADIO, RADIO_DESCRIPTION, RAW_INIT,
    SIGNAL_REMOVE, SIGNATURE, TYPE, ZHA, ZHA_GW_MSG, ZIGPY, ZIGPY_DECONZ,
    ZIGPY_XBEE)
from .device import DeviceStatus, ZHADevice
from .discovery import (
    async_create_device_entity, async_dispatch_discovery_info,
    async_process_endpoint)
from .patches import apply_application_controller_patch
from .registries import RADIO_TYPES
from .store import async_get_registry

_LOGGER = logging.getLogger(__name__)

EntityReference = collections.namedtuple(
    'EntityReference', 'reference_id zha_device cluster_channels device_info')


class ZHAGateway:
    """Gateway that handles events that happen on the ZHA Zigbee network."""

    def __init__(self, hass, config):
        """Initialize the gateway."""
        self._hass = hass
        self._config = config
        self._component = EntityComponent(_LOGGER, DOMAIN, hass)
        self._devices = {}
        self._device_registry = collections.defaultdict(list)
        self.zha_storage = None
        self.application_controller = None
        self.radio_description = None
        hass.data[DATA_ZHA][DATA_ZHA_CORE_COMPONENT] = self._component
        hass.data[DATA_ZHA][DATA_ZHA_GATEWAY] = self
        self._log_levels = {
            ORIGINAL: async_capture_log_levels(),
            CURRENT: async_capture_log_levels()
        }
        self.debug_enabled = False
        self._log_relay_handler = LogRelayHandler(hass, self)

    async def async_initialize(self, config_entry):
        """Initialize controller and connect radio."""
        self.zha_storage = await async_get_registry(self._hass)

        usb_path = config_entry.data.get(CONF_USB_PATH)
        baudrate = self._config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
        radio_type = config_entry.data.get(CONF_RADIO_TYPE)

        radio_details = RADIO_TYPES[radio_type][RADIO]()
        radio = radio_details[RADIO]
        self.radio_description = RADIO_TYPES[radio_type][RADIO_DESCRIPTION]
        await radio.connect(usb_path, baudrate)

        if CONF_DATABASE in self._config:
            database = self._config[CONF_DATABASE]
        else:
            database = os.path.join(
                self._hass.config.config_dir, DEFAULT_DATABASE_NAME)

        self.application_controller = radio_details[CONTROLLER](
            radio, database)
        apply_application_controller_patch(self)
        self.application_controller.add_listener(self)
        await self.application_controller.startup(auto_form=True)
        self._hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID] = str(
            self.application_controller.ieee)

        init_tasks = []
        for device in self.application_controller.devices.values():
            init_tasks.append(self.async_device_initialized(device, False))
        await asyncio.gather(*init_tasks)

    def device_joined(self, device):
        """Handle device joined.

        At this point, no information about the device is known other than its
        address
        """
        async_dispatcher_send(
            self._hass,
            ZHA_GW_MSG,
            {
                TYPE: DEVICE_JOINED,
                NWK: device.nwk,
                IEEE: str(device.ieee)
            }
        )

    def raw_device_initialized(self, device):
        """Handle a device initialization without quirks loaded."""
        endpoint_ids = device.endpoints.keys()
        ept_id = next((ept_id for ept_id in endpoint_ids if ept_id != 0), None)
        manufacturer = 'Unknown'
        model = 'Unknown'
        if ept_id is not None:
            manufacturer = device.endpoints[ept_id].manufacturer
            model = device.endpoints[ept_id].model
        async_dispatcher_send(
            self._hass,
            ZHA_GW_MSG,
            {
                TYPE: RAW_INIT,
                NWK: device.nwk,
                IEEE: str(device.ieee),
                MODEL: model,
                ATTR_MANUFACTURER: manufacturer,
                SIGNATURE: device.get_signature()
            }
        )

    def device_initialized(self, device):
        """Handle device joined and basic information discovered."""
        self._hass.async_create_task(
            self.async_device_initialized(device, True))

    def device_left(self, device):
        """Handle device leaving the network."""
        pass

    def device_removed(self, device):
        """Handle device being removed from the network."""
        zha_device = self._devices.pop(device.ieee, None)
        self._device_registry.pop(device.ieee, None)
        if zha_device is not None:
            device_info = async_get_device_info(self._hass, zha_device)
            self._hass.async_create_task(zha_device.async_unsub_dispatcher())
            async_dispatcher_send(
                self._hass,
                "{}_{}".format(SIGNAL_REMOVE, str(zha_device.ieee))
            )
            if device_info is not None:
                async_dispatcher_send(
                    self._hass,
                    ZHA_GW_MSG,
                    {
                        TYPE: DEVICE_REMOVED,
                        DEVICE_INFO: device_info
                    }
                )

    def get_device(self, ieee):
        """Return ZHADevice for given ieee."""
        return self._devices.get(ieee)

    def get_entity_reference(self, entity_id):
        """Return entity reference for given entity_id if found."""
        for entity_reference in itertools.chain.from_iterable(
                self.device_registry.values()):
            if entity_id == entity_reference.reference_id:
                return entity_reference

    @property
    def devices(self):
        """Return devices."""
        return self._devices

    @property
    def device_registry(self):
        """Return entities by ieee."""
        return self._device_registry

    def register_entity_reference(
            self, ieee, reference_id, zha_device, cluster_channels,
            device_info):
        """Record the creation of a hass entity associated with ieee."""
        self._device_registry[ieee].append(
            EntityReference(
                reference_id=reference_id,
                zha_device=zha_device,
                cluster_channels=cluster_channels,
                device_info=device_info
            )
        )

    @callback
    def async_enable_debug_mode(self):
        """Enable debug mode for ZHA."""
        self._log_levels[ORIGINAL] = async_capture_log_levels()
        async_set_logger_levels(DEBUG_LEVELS)
        self._log_levels[CURRENT] = async_capture_log_levels()

        for logger_name in ADD_DEVICE_RELAY_LOGGERS:
            logging.getLogger(logger_name).addHandler(self._log_relay_handler)

        self.debug_enabled = True

    @callback
    def async_disable_debug_mode(self):
        """Disable debug mode for ZHA."""
        async_set_logger_levels(self._log_levels[ORIGINAL])
        self._log_levels[CURRENT] = async_capture_log_levels()
        for logger_name in ADD_DEVICE_RELAY_LOGGERS:
            logging.getLogger(logger_name).removeHandler(
                self._log_relay_handler)
        self.debug_enabled = False

    @callback
    def _async_get_or_create_device(self, zigpy_device, is_new_join):
        """Get or create a ZHA device."""
        zha_device = self._devices.get(zigpy_device.ieee)
        if zha_device is None:
            zha_device = ZHADevice(self._hass, zigpy_device, self)
            self._devices[zigpy_device.ieee] = zha_device
        if not is_new_join:
            entry = self.zha_storage.async_get_or_create(zha_device)
            zha_device.async_update_last_seen(entry.last_seen)
            zha_device.set_power_source(entry.power_source)
        return zha_device

    @callback
    def async_device_became_available(
            self, sender, is_reply, profile, cluster, src_ep, dst_ep, tsn,
            command_id, args):
        """Handle tasks when a device becomes available."""
        self.async_update_device(sender)

    @callback
    def async_update_device(self, sender):
        """Update device that has just become available."""
        if sender.ieee in self.devices:
            device = self.devices[sender.ieee]
            # avoid a race condition during new joins
            if device.status is DeviceStatus.INITIALIZED:
                device.update_available(True)

    async def async_update_device_storage(self):
        """Update the devices in the store."""
        for device in self.devices.values():
            self.zha_storage.async_update(device)
        await self.zha_storage.async_save()

    async def async_device_initialized(self, device, is_new_join):
        """Handle device joined and basic information discovered (async)."""
        zha_device = self._async_get_or_create_device(device, is_new_join)

        discovery_infos = []
        for endpoint_id, endpoint in device.endpoints.items():
            async_process_endpoint(
                self._hass, self._config, endpoint_id, endpoint,
                discovery_infos, device, zha_device, is_new_join
            )
            if endpoint_id != 0:
                for cluster in endpoint.in_clusters.values():
                    cluster.bind_only = False
                for cluster in endpoint.out_clusters.values():
                    cluster.bind_only = True

        if is_new_join:
            # configure the device
            await zha_device.async_configure()
            zha_device.update_available(True)
        elif zha_device.power_source is not None\
                and zha_device.power_source == MAINS_POWERED:
            # the device isn't a battery powered device so we should be able
            # to update it now
            _LOGGER.debug(
                "attempting to request fresh state for %s %s",
                zha_device.name,
                "with power source: {}".format(
                    ZDOChannel.POWER_SOURCES.get(zha_device.power_source)
                )
            )
            await zha_device.async_initialize(from_cache=False)
        else:
            await zha_device.async_initialize(from_cache=True)

        for discovery_info in discovery_infos:
            async_dispatch_discovery_info(
                self._hass,
                is_new_join,
                discovery_info
            )

        device_entity = async_create_device_entity(zha_device)
        await self._component.async_add_entities([device_entity])

        if is_new_join:
            device_info = async_get_device_info(self._hass, zha_device)
            async_dispatcher_send(
                self._hass,
                ZHA_GW_MSG,
                {
                    TYPE: DEVICE_FULL_INIT,
                    DEVICE_INFO: device_info
                }
            )

    async def shutdown(self):
        """Stop ZHA Controller Application."""
        _LOGGER.debug("Shutting down ZHA ControllerApplication")
        await self.application_controller.shutdown()


@callback
def async_capture_log_levels():
    """Capture current logger levels for ZHA."""
    return {
        BELLOWS: logging.getLogger(BELLOWS).getEffectiveLevel(),
        ZHA: logging.getLogger(ZHA).getEffectiveLevel(),
        ZIGPY: logging.getLogger(ZIGPY).getEffectiveLevel(),
        ZIGPY_XBEE: logging.getLogger(ZIGPY_XBEE).getEffectiveLevel(),
        ZIGPY_DECONZ: logging.getLogger(ZIGPY_DECONZ).getEffectiveLevel(),
    }


@callback
def async_set_logger_levels(levels):
    """Set logger levels for ZHA."""
    logging.getLogger(BELLOWS).setLevel(levels[BELLOWS])
    logging.getLogger(ZHA).setLevel(levels[ZHA])
    logging.getLogger(ZIGPY).setLevel(levels[ZIGPY])
    logging.getLogger(ZIGPY_XBEE).setLevel(levels[ZIGPY_XBEE])
    logging.getLogger(ZIGPY_DECONZ).setLevel(levels[ZIGPY_DECONZ])


class LogRelayHandler(logging.Handler):
    """Log handler for error messages."""

    def __init__(self, hass, gateway):
        """Initialize a new LogErrorHandler."""
        super().__init__()
        self.hass = hass
        self.gateway = gateway

    def emit(self, record):
        """Relay log message via dispatcher."""
        stack = []
        if record.levelno >= logging.WARN:
            if not record.exc_info:
                stack = [f for f, _, _, _ in traceback.extract_stack()]

        entry = LogEntry(record, stack,
                         _figure_out_source(record, stack, self.hass))
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {
                TYPE: LOG_OUTPUT,
                LOG_ENTRY: entry.to_dict()
            }
        )
