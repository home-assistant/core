"""
Support for Zigbee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import collections
import logging
import os
import types

import voluptuous as vol

from homeassistant import config_entries, const as ha_const
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_component import EntityComponent

# Loading the config flow file will register the flow
from . import config_flow  # noqa  # pylint: disable=unused-import
from . import const as zha_const
from .event import ZhaEvent, ZhaRelayEvent
from . import api
from .helpers import convert_ieee
from .entities import ZhaDeviceEntity
from .const import (
    COMPONENTS, CONF_BAUDRATE, CONF_DATABASE, CONF_DEVICE_CONFIG,
    CONF_RADIO_TYPE, CONF_USB_PATH, DATA_ZHA, DATA_ZHA_BRIDGE_ID,
    DATA_ZHA_CONFIG, DATA_ZHA_CORE_COMPONENT, DATA_ZHA_DISPATCHERS,
    DATA_ZHA_RADIO, DEFAULT_BAUDRATE, DEFAULT_DATABASE_NAME,
    DEFAULT_RADIO_TYPE, DOMAIN, ZHA_DISCOVERY_NEW, RadioType,
    EVENTABLE_CLUSTERS, DATA_ZHA_CORE_EVENTS, ENABLE_QUIRKS,
    DEVICE_CLASS, SINGLE_INPUT_CLUSTER_DEVICE_CLASS,
    SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS, CUSTOM_CLUSTER_MAPPINGS,
    COMPONENT_CLUSTERS)

REQUIREMENTS = [
    'bellows==0.7.0',
    'zigpy==0.2.0',
    'zigpy-xbee==0.1.1',
    'zha-quirks==0.0.6'
]

DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema({
    vol.Optional(ha_const.CONF_TYPE): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(
            CONF_RADIO_TYPE,
            default=DEFAULT_RADIO_TYPE
        ): cv.enum(RadioType),
        CONF_USB_PATH: cv.string,
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
        vol.Optional(CONF_DATABASE): cv.string,
        vol.Optional(CONF_DEVICE_CONFIG, default={}):
            vol.Schema({cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}),
        vol.Optional(ENABLE_QUIRKS, default=True): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)

# Zigbee definitions
CENTICELSIUS = 'C-100'

# Internal definitions
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up ZHA from config."""
    hass.data[DATA_ZHA] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    hass.data[DATA_ZHA][DATA_ZHA_CONFIG] = conf

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': config_entries.SOURCE_IMPORT},
            data={
                CONF_USB_PATH: conf[CONF_USB_PATH],
                CONF_RADIO_TYPE: conf.get(CONF_RADIO_TYPE).value
            }
        ))
    return True


async def async_setup_entry(hass, config_entry):
    """Set up ZHA.

    Will automatically load components to support devices found on the network.
    """
    establish_device_mappings()
    hass.data[DATA_ZHA] = hass.data.get(DATA_ZHA, {})
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS] = []

    config = hass.data[DATA_ZHA].get(DATA_ZHA_CONFIG, {})

    if config.get(ENABLE_QUIRKS, True):
        # needs to be done here so that the ZHA module is finished loading
        # before zhaquirks is imported
        # pylint: disable=W0611, W0612
        import zhaquirks  # noqa

    usb_path = config_entry.data.get(CONF_USB_PATH)
    baudrate = config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
    radio_type = config_entry.data.get(CONF_RADIO_TYPE)
    if radio_type == RadioType.ezsp.name:
        import bellows.ezsp
        from bellows.zigbee.application import ControllerApplication
        radio = bellows.ezsp.EZSP()
        radio_description = "EZSP"
    elif radio_type == RadioType.xbee.name:
        import zigpy_xbee.api
        from zigpy_xbee.zigbee.application import ControllerApplication
        radio = zigpy_xbee.api.XBee()
        radio_description = "XBee"

    await radio.connect(usb_path, baudrate)
    hass.data[DATA_ZHA][DATA_ZHA_RADIO] = radio

    if CONF_DATABASE in config:
        database = config[CONF_DATABASE]
    else:
        database = os.path.join(hass.config.config_dir, DEFAULT_DATABASE_NAME)

    # patch zigpy listener to prevent flooding logs with warnings due to
    # how zigpy implemented its listeners
    from zigpy.appdb import ClusterPersistingListener

    def zha_send_event(self, cluster, command, args):
        pass

    ClusterPersistingListener.zha_send_event = types.MethodType(
        zha_send_event,
        ClusterPersistingListener
    )

    application_controller = ControllerApplication(radio, database)
    listener = ApplicationListener(hass, config)
    application_controller.add_listener(listener)
    await application_controller.startup(auto_form=True)

    for device in application_controller.devices.values():
        hass.async_create_task(
            listener.async_device_initialized(device, False))

    device_registry = await \
        hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_ZIGBEE, str(application_controller.ieee))},
        identifiers={(DOMAIN, str(application_controller.ieee))},
        name="Zigbee Coordinator",
        manufacturer="ZHA",
        model=radio_description,
    )

    hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID] = str(application_controller.ieee)

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                config_entry, component)
        )

    api.async_load_api(hass, application_controller, listener)

    def zha_shutdown(event):
        """Close radio."""
        hass.data[DATA_ZHA][DATA_ZHA_RADIO].close()

    hass.bus.async_listen_once(ha_const.EVENT_HOMEASSISTANT_STOP, zha_shutdown)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload ZHA config entry."""
    api.async_unload_api(hass)

    dispatchers = hass.data[DATA_ZHA].get(DATA_ZHA_DISPATCHERS, [])
    for unsub_dispatcher in dispatchers:
        unsub_dispatcher()

    for component in COMPONENTS:
        await hass.config_entries.async_forward_entry_unload(
            config_entry, component)

    # clean up device entities
    component = hass.data[DATA_ZHA][DATA_ZHA_CORE_COMPONENT]
    entity_ids = [entity.entity_id for entity in component.entities]
    for entity_id in entity_ids:
        await component.async_remove_entity(entity_id)

    # clean up events
    hass.data[DATA_ZHA][DATA_ZHA_CORE_EVENTS].clear()

    _LOGGER.debug("Closing zha radio")
    hass.data[DATA_ZHA][DATA_ZHA_RADIO].close()

    del hass.data[DATA_ZHA]
    return True


def establish_device_mappings():
    """Establish mappings between ZCL objects and HA ZHA objects.

    These cannot be module level, as importing bellows must be done in a
    in a function.
    """
    from zigpy import zcl, quirks
    from zigpy.profiles import PROFILES, zha, zll
    from .sensor import RelativeHumiditySensor

    if zha.PROFILE_ID not in DEVICE_CLASS:
        DEVICE_CLASS[zha.PROFILE_ID] = {}
    if zll.PROFILE_ID not in DEVICE_CLASS:
        DEVICE_CLASS[zll.PROFILE_ID] = {}

    EVENTABLE_CLUSTERS.append(zcl.clusters.general.AnalogInput.cluster_id)
    EVENTABLE_CLUSTERS.append(zcl.clusters.general.LevelControl.cluster_id)
    EVENTABLE_CLUSTERS.append(zcl.clusters.general.MultistateInput.cluster_id)
    EVENTABLE_CLUSTERS.append(zcl.clusters.general.OnOff.cluster_id)

    DEVICE_CLASS[zha.PROFILE_ID].update({
        zha.DeviceType.ON_OFF_SWITCH: 'binary_sensor',
        zha.DeviceType.LEVEL_CONTROL_SWITCH: 'binary_sensor',
        zha.DeviceType.REMOTE_CONTROL: 'binary_sensor',
        zha.DeviceType.SMART_PLUG: 'switch',
        zha.DeviceType.LEVEL_CONTROLLABLE_OUTPUT: 'light',
        zha.DeviceType.ON_OFF_LIGHT: 'light',
        zha.DeviceType.DIMMABLE_LIGHT: 'light',
        zha.DeviceType.COLOR_DIMMABLE_LIGHT: 'light',
        zha.DeviceType.ON_OFF_LIGHT_SWITCH: 'binary_sensor',
        zha.DeviceType.DIMMER_SWITCH: 'binary_sensor',
        zha.DeviceType.COLOR_DIMMER_SWITCH: 'binary_sensor',
    })
    DEVICE_CLASS[zll.PROFILE_ID].update({
        zll.DeviceType.ON_OFF_LIGHT: 'light',
        zll.DeviceType.ON_OFF_PLUGIN_UNIT: 'switch',
        zll.DeviceType.DIMMABLE_LIGHT: 'light',
        zll.DeviceType.DIMMABLE_PLUGIN_UNIT: 'light',
        zll.DeviceType.COLOR_LIGHT: 'light',
        zll.DeviceType.EXTENDED_COLOR_LIGHT: 'light',
        zll.DeviceType.COLOR_TEMPERATURE_LIGHT: 'light',
        zll.DeviceType.COLOR_CONTROLLER: 'binary_sensor',
        zll.DeviceType.COLOR_SCENE_CONTROLLER: 'binary_sensor',
        zll.DeviceType.CONTROLLER: 'binary_sensor',
        zll.DeviceType.SCENE_CONTROLLER: 'binary_sensor',
        zll.DeviceType.ON_OFF_SENSOR: 'binary_sensor',
    })

    SINGLE_INPUT_CLUSTER_DEVICE_CLASS.update({
        zcl.clusters.general.OnOff: 'switch',
        zcl.clusters.measurement.RelativeHumidity: 'sensor',
        zcl.clusters.measurement.TemperatureMeasurement: 'sensor',
        zcl.clusters.measurement.PressureMeasurement: 'sensor',
        zcl.clusters.measurement.IlluminanceMeasurement: 'sensor',
        zcl.clusters.smartenergy.Metering: 'sensor',
        zcl.clusters.homeautomation.ElectricalMeasurement: 'sensor',
        zcl.clusters.general.PowerConfiguration: 'sensor',
        zcl.clusters.security.IasZone: 'binary_sensor',
        zcl.clusters.measurement.OccupancySensing: 'binary_sensor',
        zcl.clusters.hvac.Fan: 'fan',
    })
    SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS.update({
        zcl.clusters.general.OnOff: 'binary_sensor',
    })

    # A map of device/cluster to component/sub-component
    CUSTOM_CLUSTER_MAPPINGS.update({
        (quirks.smartthings.SmartthingsTemperatureHumiditySensor, 64581):
            ('sensor', RelativeHumiditySensor)
    })

    # A map of hass components to all Zigbee clusters it could use
    for profile_id, classes in DEVICE_CLASS.items():
        profile = PROFILES[profile_id]
        for device_type, component in classes.items():
            if component not in COMPONENT_CLUSTERS:
                COMPONENT_CLUSTERS[component] = (set(), set())
            clusters = profile.CLUSTERS[device_type]
            COMPONENT_CLUSTERS[component][0].update(clusters[0])
            COMPONENT_CLUSTERS[component][1].update(clusters[1])


class ApplicationListener:
    """All handlers for events that happen on the ZigBee application."""

    def __init__(self, hass, config):
        """Initialize the listener."""
        self._hass = hass
        self._config = config
        self._component = EntityComponent(_LOGGER, DOMAIN, hass)
        self._device_registry = collections.defaultdict(list)
        self._events = {}

        for component in COMPONENTS:
            hass.data[DATA_ZHA][component] = (
                hass.data[DATA_ZHA].get(component, {})
            )
        hass.data[DATA_ZHA][DATA_ZHA_CORE_COMPONENT] = self._component
        hass.data[DATA_ZHA][DATA_ZHA_CORE_EVENTS] = self._events

    def device_joined(self, device):
        """Handle device joined.

        At this point, no information about the device is known other than its
        address
        """
        # Wait for device_initialized, instead
        pass

    def raw_device_initialized(self, device):
        """Handle a device initialization without quirks loaded."""
        # Wait for device_initialized, instead
        pass

    def device_initialized(self, device):
        """Handle device joined and basic information discovered."""
        self._hass.async_create_task(
            self.async_device_initialized(device, True))

    def device_left(self, device):
        """Handle device leaving the network."""
        pass

    def device_removed(self, device):
        """Handle device being removed from the network."""
        for device_entity in self._device_registry[device.ieee]:
            self._hass.async_create_task(device_entity.async_remove())
        if device.ieee in self._events:
            self._events.pop(device.ieee)

    def get_device_entity(self, ieee_str):
        """Return ZHADeviceEntity for given ieee."""
        ieee = convert_ieee(ieee_str)
        if ieee in self._device_registry:
            entities = self._device_registry[ieee]
            entity = next(
                ent for ent in entities if isinstance(ent, ZhaDeviceEntity))
            return entity
        return None

    def get_entities_for_ieee(self, ieee_str):
        """Return list of entities for given ieee."""
        ieee = convert_ieee(ieee_str)
        if ieee in self._device_registry:
            return self._device_registry[ieee]
        return []

    @property
    def device_registry(self) -> str:
        """Return devices."""
        return self._device_registry

    async def async_device_initialized(self, device, join):
        """Handle device joined and basic information discovered (async)."""
        import zigpy.profiles

        device_manufacturer = device_model = None

        for endpoint_id, endpoint in device.endpoints.items():
            if endpoint_id == 0:  # ZDO
                continue

            if endpoint.manufacturer is not None:
                device_manufacturer = endpoint.manufacturer
            if endpoint.model is not None:
                device_model = endpoint.model

            component = None
            profile_clusters = ([], [])
            device_key = "{}-{}".format(device.ieee, endpoint_id)
            node_config = {}
            if CONF_DEVICE_CONFIG in self._config:
                node_config = self._config[CONF_DEVICE_CONFIG].get(
                    device_key, {}
                )

            if endpoint.profile_id in zigpy.profiles.PROFILES:
                profile = zigpy.profiles.PROFILES[endpoint.profile_id]
                if zha_const.DEVICE_CLASS.get(endpoint.profile_id,
                                              {}).get(endpoint.device_type,
                                                      None):
                    profile_clusters = profile.CLUSTERS[endpoint.device_type]
                    profile_info = zha_const.DEVICE_CLASS[endpoint.profile_id]
                    component = profile_info[endpoint.device_type]

            if ha_const.CONF_TYPE in node_config:
                component = node_config[ha_const.CONF_TYPE]
                profile_clusters = zha_const.COMPONENT_CLUSTERS[component]

            if component:
                in_clusters = [endpoint.in_clusters[c]
                               for c in profile_clusters[0]
                               if c in endpoint.in_clusters]
                out_clusters = [endpoint.out_clusters[c]
                                for c in profile_clusters[1]
                                if c in endpoint.out_clusters]
                discovery_info = {
                    'application_listener': self,
                    'endpoint': endpoint,
                    'in_clusters': {c.cluster_id: c for c in in_clusters},
                    'out_clusters': {c.cluster_id: c for c in out_clusters},
                    'manufacturer': endpoint.manufacturer,
                    'model': endpoint.model,
                    'new_join': join,
                    'unique_id': device_key,
                }

                if join:
                    async_dispatcher_send(
                        self._hass,
                        ZHA_DISCOVERY_NEW.format(component),
                        discovery_info
                    )
                else:
                    self._hass.data[DATA_ZHA][component][device_key] = (
                        discovery_info
                    )

            for cluster in endpoint.in_clusters.values():
                await self._attempt_single_cluster_device(
                    endpoint,
                    cluster,
                    profile_clusters[0],
                    device_key,
                    zha_const.SINGLE_INPUT_CLUSTER_DEVICE_CLASS,
                    'in_clusters',
                    join,
                )

            for cluster in endpoint.out_clusters.values():
                await self._attempt_single_cluster_device(
                    endpoint,
                    cluster,
                    profile_clusters[1],
                    device_key,
                    zha_const.SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS,
                    'out_clusters',
                    join,
                )

        endpoint_entity = ZhaDeviceEntity(
            device,
            device_manufacturer,
            device_model,
            self,
        )
        await self._component.async_add_entities([endpoint_entity])

    def register_entity(self, ieee, entity_obj):
        """Record the creation of a hass entity associated with ieee."""
        self._device_registry[ieee].append(entity_obj)

    async def _attempt_single_cluster_device(self, endpoint, cluster,
                                             profile_clusters, device_key,
                                             device_classes, discovery_attr,
                                             is_new_join):
        """Try to set up an entity from a "bare" cluster."""
        if cluster.cluster_id in EVENTABLE_CLUSTERS:
            if cluster.endpoint.device.ieee not in self._events:
                self._events.update({cluster.endpoint.device.ieee: []})
            from zigpy.zcl.clusters.general import OnOff, LevelControl
            if discovery_attr == 'out_clusters' and \
                    (cluster.cluster_id == OnOff.cluster_id or
                     cluster.cluster_id == LevelControl.cluster_id):
                self._events[cluster.endpoint.device.ieee].append(
                    ZhaRelayEvent(self._hass, cluster)
                )
            else:
                self._events[cluster.endpoint.device.ieee].append(ZhaEvent(
                    self._hass,
                    cluster
                ))

        if cluster.cluster_id in profile_clusters:
            return

        component = sub_component = None
        for cluster_type, candidate_component in device_classes.items():
            if isinstance(cluster, cluster_type):
                component = candidate_component
                break

        for signature, comp in zha_const.CUSTOM_CLUSTER_MAPPINGS.items():
            if (isinstance(endpoint.device, signature[0]) and
                    cluster.cluster_id == signature[1]):
                component = comp[0]
                sub_component = comp[1]
                break

        if component is None:
            return

        cluster_key = "{}-{}".format(device_key, cluster.cluster_id)
        discovery_info = {
            'application_listener': self,
            'endpoint': endpoint,
            'in_clusters': {},
            'out_clusters': {},
            'manufacturer': endpoint.manufacturer,
            'model': endpoint.model,
            'new_join': is_new_join,
            'unique_id': cluster_key,
            'entity_suffix': '_{}'.format(cluster.cluster_id),
        }
        discovery_info[discovery_attr] = {cluster.cluster_id: cluster}
        if sub_component:
            discovery_info.update({'sub_component': sub_component})

        if is_new_join:
            async_dispatcher_send(
                self._hass,
                ZHA_DISCOVERY_NEW.format(component),
                discovery_info
            )
        else:
            self._hass.data[DATA_ZHA][component][cluster_key] = discovery_info
