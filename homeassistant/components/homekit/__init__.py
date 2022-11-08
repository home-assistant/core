"""Support for Apple HomeKit."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from copy import deepcopy
import ipaddress
import logging
import os
from typing import Any, cast

from aiohttp import web
from pyhap.characteristic import Characteristic
from pyhap.const import STANDALONE_AID
from pyhap.loader import get_loader
from pyhap.service import Service
import voluptuous as vol
from zeroconf.asyncio import AsyncZeroconf

from homeassistant.components import device_automation, network, zeroconf
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.humidifier import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.components.network import MDNS_TARGET_IP
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_HW_VERSION,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SW_VERSION,
    CONF_DEVICES,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_RELOAD,
)
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, State, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import device_registry, entity_registry, instance_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    BASE_FILTER_SCHEMA,
    FILTER_SCHEMA,
    EntityFilter,
)
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import (
    async_extract_referenced_entity_ids,
    async_register_admin_service,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound, async_get_integration

from . import (  # noqa: F401
    type_cameras,
    type_covers,
    type_fans,
    type_humidifiers,
    type_lights,
    type_locks,
    type_media_players,
    type_remotes,
    type_security_systems,
    type_sensors,
    type_switches,
    type_thermostats,
)
from .accessories import HomeAccessory, HomeBridge, HomeDriver, get_accessory
from .aidmanager import AccessoryAidStorage
from .const import (
    ATTR_INTEGRATION,
    BRIDGE_NAME,
    BRIDGE_SERIAL_NUMBER,
    CONF_ADVERTISE_IP,
    CONF_ENTITY_CONFIG,
    CONF_ENTRY_INDEX,
    CONF_EXCLUDE_ACCESSORY_MODE,
    CONF_FILTER,
    CONF_HOMEKIT_MODE,
    CONF_LINKED_BATTERY_CHARGING_SENSOR,
    CONF_LINKED_BATTERY_SENSOR,
    CONF_LINKED_DOORBELL_SENSOR,
    CONF_LINKED_HUMIDITY_SENSOR,
    CONF_LINKED_MOTION_SENSOR,
    CONFIG_OPTIONS,
    DEFAULT_EXCLUDE_ACCESSORY_MODE,
    DEFAULT_HOMEKIT_MODE,
    DEFAULT_PORT,
    DOMAIN,
    HOMEKIT,
    HOMEKIT_MODE_ACCESSORY,
    HOMEKIT_MODES,
    HOMEKIT_PAIRING_QR,
    HOMEKIT_PAIRING_QR_SECRET,
    MANUFACTURER,
    PERSIST_LOCK,
    SERVICE_HOMEKIT_RESET_ACCESSORY,
    SERVICE_HOMEKIT_UNPAIR,
    SHUTDOWN_TIMEOUT,
)
from .iidmanager import AccessoryIIDStorage
from .type_triggers import DeviceTriggerAccessory
from .util import (
    accessory_friendly_name,
    async_dismiss_setup_message,
    async_port_is_available,
    async_show_setup_message,
    get_persist_fullpath_for_entry_id,
    remove_state_files_for_entry_id,
    state_needs_accessory_mode,
    validate_entity_config,
)

_LOGGER = logging.getLogger(__name__)

MAX_DEVICES = 150  # includes the bridge

# #### Driver Status ####
STATUS_READY = 0
STATUS_RUNNING = 1
STATUS_STOPPED = 2
STATUS_WAIT = 3

PORT_CLEANUP_CHECK_INTERVAL_SECS = 1

_HOMEKIT_CONFIG_UPDATE_TIME = (
    10  # number of seconds to wait for homekit to see the c# change
)


def _has_all_unique_names_and_ports(
    bridges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate that each homekit bridge configured has a unique name."""
    names = [bridge[CONF_NAME] for bridge in bridges]
    ports = [bridge[CONF_PORT] for bridge in bridges]
    vol.Schema(vol.Unique())(names)
    vol.Schema(vol.Unique())(ports)
    return bridges


BRIDGE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_HOMEKIT_MODE, default=DEFAULT_HOMEKIT_MODE): vol.In(
                HOMEKIT_MODES
            ),
            vol.Optional(CONF_NAME, default=BRIDGE_NAME): vol.All(
                cv.string, vol.Length(min=3, max=25)
            ),
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_IP_ADDRESS): vol.All(ipaddress.ip_address, cv.string),
            vol.Optional(CONF_ADVERTISE_IP): vol.All(ipaddress.ip_address, cv.string),
            vol.Optional(CONF_FILTER, default={}): BASE_FILTER_SCHEMA,
            vol.Optional(CONF_ENTITY_CONFIG, default={}): validate_entity_config,
            vol.Optional(CONF_DEVICES): cv.ensure_list,
        },
        extra=vol.ALLOW_EXTRA,
    ),
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [BRIDGE_SCHEMA], _has_all_unique_names_and_ports)},
    extra=vol.ALLOW_EXTRA,
)


RESET_ACCESSORY_SERVICE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_ids}
)


UNPAIR_SERVICE_SCHEMA = vol.All(
    vol.Schema(cv.ENTITY_SERVICE_FIELDS),
    cv.has_at_least_one_key(ATTR_DEVICE_ID),
)


def _async_all_homekit_instances(hass: HomeAssistant) -> list[HomeKit]:
    """All active HomeKit instances."""
    return [
        data[HOMEKIT]
        for data in hass.data[DOMAIN].values()
        if isinstance(data, dict) and HOMEKIT in data
    ]


def _async_get_imported_entries_indices(
    current_entries: list[ConfigEntry],
) -> tuple[dict[str, ConfigEntry], dict[int, ConfigEntry]]:
    """Return a dicts of the entries by name and port."""

    # For backwards compat, its possible the first bridge is using the default
    # name.
    entries_by_name: dict[str, ConfigEntry] = {}
    entries_by_port: dict[int, ConfigEntry] = {}
    for entry in current_entries:
        if entry.source != SOURCE_IMPORT:
            continue
        entries_by_name[entry.data.get(CONF_NAME, BRIDGE_NAME)] = entry
        entries_by_port[entry.data.get(CONF_PORT, DEFAULT_PORT)] = entry
    return entries_by_name, entries_by_port


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomeKit from yaml."""
    hass.data.setdefault(DOMAIN, {})[PERSIST_LOCK] = asyncio.Lock()

    # Initialize the loader before loading entries to ensure
    # there is no race where multiple entries try to load it
    # at the same time.
    await hass.async_add_executor_job(get_loader)

    _async_register_events_and_services(hass)

    if DOMAIN not in config:
        return True

    current_entries = hass.config_entries.async_entries(DOMAIN)
    entries_by_name, entries_by_port = _async_get_imported_entries_indices(
        current_entries
    )

    for index, conf in enumerate(config[DOMAIN]):
        if _async_update_config_entry_from_yaml(
            hass, entries_by_name, entries_by_port, conf
        ):
            continue

        conf[CONF_ENTRY_INDEX] = index
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=conf,
            )
        )

    return True


@callback
def _async_update_config_entry_from_yaml(
    hass: HomeAssistant,
    entries_by_name: dict[str, ConfigEntry],
    entries_by_port: dict[int, ConfigEntry],
    conf: ConfigType,
) -> bool:
    """Update a config entry with the latest yaml.

    Returns True if a matching config entry was found

    Returns False if there is no matching config entry
    """
    if not (
        matching_entry := entries_by_name.get(conf.get(CONF_NAME, BRIDGE_NAME))
        or entries_by_port.get(conf.get(CONF_PORT, DEFAULT_PORT))
    ):
        return False

    # If they alter the yaml config we import the changes
    # since there currently is no practical way to support
    # all the options in the UI at this time.
    data = conf.copy()
    options = {}
    for key in CONFIG_OPTIONS:
        if key in data:
            options[key] = data[key]
            del data[key]

    hass.config_entries.async_update_entry(matching_entry, data=data, options=options)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomeKit from a config entry."""
    _async_import_options_from_data_if_missing(hass, entry)

    conf = entry.data
    options = entry.options

    name = conf[CONF_NAME]
    port = conf[CONF_PORT]
    _LOGGER.debug("Begin setup HomeKit for %s", name)

    # ip_address and advertise_ip are yaml only
    ip_address = conf.get(
        CONF_IP_ADDRESS, await network.async_get_source_ip(hass, MDNS_TARGET_IP)
    )
    advertise_ip = conf.get(CONF_ADVERTISE_IP)
    # exclude_accessory_mode is only used for config flow
    # to indicate that the config entry was setup after
    # we started creating config entries for entities that
    # to run in accessory mode and that we should never include
    # these entities on the bridge. For backwards compatibility
    # with users who have not migrated yet we do not do exclude
    # these entities by default as we cannot migrate automatically
    # since it requires a re-pairing.
    exclude_accessory_mode = conf.get(
        CONF_EXCLUDE_ACCESSORY_MODE, DEFAULT_EXCLUDE_ACCESSORY_MODE
    )
    homekit_mode = options.get(CONF_HOMEKIT_MODE, DEFAULT_HOMEKIT_MODE)
    entity_config = options.get(CONF_ENTITY_CONFIG, {}).copy()
    entity_filter = FILTER_SCHEMA(options.get(CONF_FILTER, {}))
    devices = options.get(CONF_DEVICES, [])

    homekit = HomeKit(
        hass,
        name,
        port,
        ip_address,
        entity_filter,
        exclude_accessory_mode,
        entity_config,
        homekit_mode,
        advertise_ip,
        entry.entry_id,
        entry.title,
        devices=devices,
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, homekit.async_stop)
    )

    hass.data[DOMAIN][entry.entry_id] = {HOMEKIT: homekit}

    if hass.state == CoreState.running:
        await homekit.async_start()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, homekit.async_start)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    if entry.source == SOURCE_IMPORT:
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    async_dismiss_setup_message(hass, entry.entry_id)
    homekit = hass.data[DOMAIN][entry.entry_id][HOMEKIT]

    if homekit.status == STATUS_RUNNING:
        await homekit.async_stop()

    logged_shutdown_wait = False
    for _ in range(0, SHUTDOWN_TIMEOUT):
        if async_port_is_available(entry.data[CONF_PORT]):
            break

        if not logged_shutdown_wait:
            _LOGGER.info("Waiting for the HomeKit server to shutdown")
            logged_shutdown_wait = True

        await asyncio.sleep(PORT_CLEANUP_CHECK_INTERVAL_SECS)

    hass.data[DOMAIN].pop(entry.entry_id)

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    await hass.async_add_executor_job(
        remove_state_files_for_entry_id, hass, entry.entry_id
    )


@callback
def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    options = deepcopy(dict(entry.options))
    data = deepcopy(dict(entry.data))
    modified = False
    for importable_option in CONFIG_OPTIONS:
        if importable_option not in entry.options and importable_option in entry.data:
            options[importable_option] = entry.data[importable_option]
            del data[importable_option]
            modified = True

    if modified:
        hass.config_entries.async_update_entry(entry, data=data, options=options)


@callback
def _async_register_events_and_services(hass: HomeAssistant) -> None:
    """Register events and services for HomeKit."""
    hass.http.register_view(HomeKitPairingQRView)

    async def async_handle_homekit_reset_accessory(service: ServiceCall) -> None:
        """Handle reset accessory HomeKit service call."""
        for homekit in _async_all_homekit_instances(hass):
            if homekit.status != STATUS_RUNNING:
                _LOGGER.warning(
                    "HomeKit is not running. Either it is waiting to be "
                    "started or has been stopped"
                )
                continue

            entity_ids = cast(list[str], service.data.get("entity_id"))
            await homekit.async_reset_accessories(entity_ids)

    hass.services.async_register(
        DOMAIN,
        SERVICE_HOMEKIT_RESET_ACCESSORY,
        async_handle_homekit_reset_accessory,
        schema=RESET_ACCESSORY_SERVICE_SCHEMA,
    )

    async def async_handle_homekit_unpair(service: ServiceCall) -> None:
        """Handle unpair HomeKit service call."""
        referenced = async_extract_referenced_entity_ids(hass, service)
        dev_reg = device_registry.async_get(hass)
        for device_id in referenced.referenced_devices:
            if not (dev_reg_ent := dev_reg.async_get(device_id)):
                raise HomeAssistantError(f"No device found for device id: {device_id}")
            macs = [
                cval
                for ctype, cval in dev_reg_ent.connections
                if ctype == device_registry.CONNECTION_NETWORK_MAC
            ]
            matching_instances = [
                homekit
                for homekit in _async_all_homekit_instances(hass)
                if homekit.driver
                and device_registry.format_mac(homekit.driver.state.mac) in macs
            ]
            if not matching_instances:
                raise HomeAssistantError(
                    f"No homekit accessory found for device id: {device_id}"
                )
            for homekit in matching_instances:
                homekit.async_unpair()

    hass.services.async_register(
        DOMAIN,
        SERVICE_HOMEKIT_UNPAIR,
        async_handle_homekit_unpair,
        schema=UNPAIR_SERVICE_SCHEMA,
    )

    async def _handle_homekit_reload(service: ServiceCall) -> None:
        """Handle start HomeKit service call."""
        config = await async_integration_yaml_config(hass, DOMAIN)

        if not config or DOMAIN not in config:
            return

        current_entries = hass.config_entries.async_entries(DOMAIN)
        entries_by_name, entries_by_port = _async_get_imported_entries_indices(
            current_entries
        )

        for conf in config[DOMAIN]:
            _async_update_config_entry_from_yaml(
                hass, entries_by_name, entries_by_port, conf
            )

        reload_tasks = [
            hass.config_entries.async_reload(entry.entry_id)
            for entry in current_entries
        ]

        await asyncio.gather(*reload_tasks)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        _handle_homekit_reload,
    )


class HomeKit:
    """Class to handle all actions between HomeKit and Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        port: int,
        ip_address: str | None,
        entity_filter: EntityFilter,
        exclude_accessory_mode: bool,
        entity_config: dict,
        homekit_mode: str,
        advertise_ip: str | None,
        entry_id: str,
        entry_title: str,
        devices: list[str] | None = None,
    ) -> None:
        """Initialize a HomeKit object."""
        self.hass = hass
        self._name = name
        self._port = port
        self._ip_address = ip_address
        self._filter = entity_filter
        self._config = entity_config
        self._exclude_accessory_mode = exclude_accessory_mode
        self._advertise_ip = advertise_ip
        self._entry_id = entry_id
        self._entry_title = entry_title
        self._homekit_mode = homekit_mode
        self._devices = devices or []
        self.aid_storage: AccessoryAidStorage | None = None
        self.iid_storage: AccessoryIIDStorage | None = None
        self.status = STATUS_READY
        self.driver: HomeDriver | None = None
        self.bridge: HomeBridge | None = None
        self._reset_lock = asyncio.Lock()

    def setup(self, async_zeroconf_instance: AsyncZeroconf, uuid: str) -> None:
        """Set up bridge and accessory driver."""
        assert self.iid_storage is not None
        persist_file = get_persist_fullpath_for_entry_id(self.hass, self._entry_id)

        self.driver = HomeDriver(
            self.hass,
            self._entry_id,
            self._name,
            self._entry_title,
            loop=self.hass.loop,
            address=self._ip_address,
            port=self._port,
            persist_file=persist_file,
            advertised_address=self._advertise_ip,
            async_zeroconf_instance=async_zeroconf_instance,
            zeroconf_server=f"{uuid}-hap.local.",
            loader=get_loader(),
            iid_storage=self.iid_storage,
        )

        # If we do not load the mac address will be wrong
        # as pyhap uses a random one until state is restored
        if os.path.exists(persist_file):
            self.driver.load()

    async def async_reset_accessories(self, entity_ids: Iterable[str]) -> None:
        """Reset the accessory to load the latest configuration."""
        async with self._reset_lock:
            if not self.bridge:
                await self.async_reset_accessories_in_accessory_mode(entity_ids)
                return
            await self.async_reset_accessories_in_bridge_mode(entity_ids)

    async def _async_shutdown_accessory(self, accessory: HomeAccessory) -> None:
        """Shutdown an accessory."""
        assert self.driver is not None
        await accessory.stop()
        # Deallocate the IIDs for the accessory
        iid_manager = accessory.iid_manager
        services: list[Service] = accessory.services
        for service in services:
            iid_manager.remove_obj(service)
            characteristics: list[Characteristic] = service.characteristics
            for char in characteristics:
                iid_manager.remove_obj(char)

    async def async_reset_accessories_in_accessory_mode(
        self, entity_ids: Iterable[str]
    ) -> None:
        """Reset accessories in accessory mode."""
        assert self.driver is not None

        acc = cast(HomeAccessory, self.driver.accessory)
        if acc.entity_id not in entity_ids:
            return
        if not (state := self.hass.states.get(acc.entity_id)):
            _LOGGER.warning(
                "The underlying entity %s disappeared during reset", acc.entity_id
            )
            return
        await self._async_shutdown_accessory(acc)
        if new_acc := self._async_create_single_accessory([state]):
            self.driver.accessory = new_acc
            self.hass.async_add_job(new_acc.run)
            await self.async_config_changed()

    async def async_reset_accessories_in_bridge_mode(
        self, entity_ids: Iterable[str]
    ) -> None:
        """Reset accessories in bridge mode."""
        assert self.aid_storage is not None
        assert self.bridge is not None
        assert self.driver is not None

        new = []
        acc: HomeAccessory | None
        for entity_id in entity_ids:
            aid = self.aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
            if aid not in self.bridge.accessories:
                continue
            _LOGGER.info(
                "HomeKit Bridge %s will reset accessory with linked entity_id %s",
                self._name,
                entity_id,
            )
            acc = await self.async_remove_bridge_accessory(aid)
            if acc:
                await self._async_shutdown_accessory(acc)
            if acc and (state := self.hass.states.get(acc.entity_id)):
                new.append(state)
            else:
                _LOGGER.warning(
                    "The underlying entity %s disappeared during reset", entity_id
                )

        if not new:
            # No matched accessories, probably on another bridge
            return

        await self.async_config_changed()
        await asyncio.sleep(_HOMEKIT_CONFIG_UPDATE_TIME)
        for state in new:
            if acc := self.add_bridge_accessory(state):
                self.hass.async_add_job(acc.run)
        await self.async_config_changed()

    async def async_config_changed(self) -> None:
        """Call config changed which writes out the new config to disk."""
        assert self.driver is not None
        await self.hass.async_add_executor_job(self.driver.config_changed)

    def add_bridge_accessory(self, state: State) -> HomeAccessory | None:
        """Try adding accessory to bridge if configured beforehand."""
        assert self.driver is not None

        if self._would_exceed_max_devices(state.entity_id):
            return None

        if state_needs_accessory_mode(state):
            if self._exclude_accessory_mode:
                return None
            _LOGGER.warning(
                "The bridge %s has entity %s. For best performance, "
                "and to prevent unexpected unavailability, create and "
                "pair a separate HomeKit instance in accessory mode for "
                "this entity",
                self._name,
                state.entity_id,
            )

        assert self.aid_storage is not None
        assert self.bridge is not None
        aid = self.aid_storage.get_or_allocate_aid_for_entity_id(state.entity_id)
        conf = self._config.get(state.entity_id, {}).copy()
        # If an accessory cannot be created or added due to an exception
        # of any kind (usually in pyhap) it should not prevent
        # the rest of the accessories from being created
        try:
            acc = get_accessory(self.hass, self.driver, state, aid, conf)
            if acc is not None:
                self.bridge.add_accessory(acc)
                return acc
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Failed to create a HomeKit accessory for %s", state.entity_id
            )
        return None

    def _would_exceed_max_devices(self, name: str | None) -> bool:
        """Check if adding another devices would reach the limit and log."""
        # The bridge itself counts as an accessory
        assert self.bridge is not None
        if len(self.bridge.accessories) + 1 >= MAX_DEVICES:
            _LOGGER.warning(
                "Cannot add %s as this would exceed the %d device limit. Consider using the filter option",
                name,
                MAX_DEVICES,
            )
            return True
        return False

    def add_bridge_triggers_accessory(
        self, device: device_registry.DeviceEntry, device_triggers: list[dict[str, Any]]
    ) -> None:
        """Add device automation triggers to the bridge."""
        if self._would_exceed_max_devices(device.name):
            return

        assert self.aid_storage is not None
        assert self.bridge is not None
        aid = self.aid_storage.get_or_allocate_aid(device.id, device.id)
        # If an accessory cannot be created or added due to an exception
        # of any kind (usually in pyhap) it should not prevent
        # the rest of the accessories from being created
        config: dict[str, Any] = {}
        self._fill_config_from_device_registry_entry(device, config)
        self.bridge.add_accessory(
            DeviceTriggerAccessory(
                self.hass,
                self.driver,
                device.name,
                None,
                aid,
                config,
                device_id=device.id,
                device_triggers=device_triggers,
            )
        )

    async def async_remove_bridge_accessory(self, aid: int) -> HomeAccessory | None:
        """Try adding accessory to bridge if configured beforehand."""
        assert self.bridge is not None
        if acc := self.bridge.accessories.pop(aid, None):
            return cast(HomeAccessory, acc)
        return None

    async def async_configure_accessories(self) -> list[State]:
        """Configure accessories for the included states."""
        dev_reg = device_registry.async_get(self.hass)
        ent_reg = entity_registry.async_get(self.hass)
        device_lookup = ent_reg.async_get_device_class_lookup(
            {
                (BINARY_SENSOR_DOMAIN, BinarySensorDeviceClass.BATTERY_CHARGING),
                (BINARY_SENSOR_DOMAIN, BinarySensorDeviceClass.MOTION),
                (BINARY_SENSOR_DOMAIN, BinarySensorDeviceClass.OCCUPANCY),
                (SENSOR_DOMAIN, SensorDeviceClass.BATTERY),
                (SENSOR_DOMAIN, SensorDeviceClass.HUMIDITY),
            }
        )

        entity_states = []
        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            if not self._filter(entity_id):
                continue

            if ent_reg_ent := ent_reg.async_get(entity_id):
                if (
                    ent_reg_ent.entity_category is not None
                    or ent_reg_ent.hidden_by is not None
                ) and not self._filter.explicitly_included(entity_id):
                    continue

                await self._async_set_device_info_attributes(
                    ent_reg_ent, dev_reg, entity_id
                )
                self._async_configure_linked_sensors(ent_reg_ent, device_lookup, state)

            entity_states.append(state)

        return entity_states

    async def async_start(self, *args: Any) -> None:
        """Load storage and start."""
        if self.status != STATUS_READY:
            return
        self.status = STATUS_WAIT
        async_zc_instance = await zeroconf.async_get_async_instance(self.hass)
        uuid = await instance_id.async_get(self.hass)
        self.aid_storage = AccessoryAidStorage(self.hass, self._entry_id)
        self.iid_storage = AccessoryIIDStorage(self.hass, self._entry_id)
        # Avoid gather here since it will be I/O bound anyways
        await self.aid_storage.async_initialize()
        await self.iid_storage.async_initialize()
        await self.hass.async_add_executor_job(self.setup, async_zc_instance, uuid)
        assert self.driver is not None

        if not await self._async_create_accessories():
            return
        self._async_register_bridge()
        _LOGGER.debug("Driver start for %s", self._name)
        await self.driver.async_start()
        async with self.hass.data[DOMAIN][PERSIST_LOCK]:
            await self.hass.async_add_executor_job(self.driver.persist)
        self.status = STATUS_RUNNING

        if self.driver.state.paired:
            return
        self._async_show_setup_message()

    @callback
    def _async_show_setup_message(self) -> None:
        """Show the pairing setup message."""
        assert self.driver is not None

        async_show_setup_message(
            self.hass,
            self._entry_id,
            accessory_friendly_name(self._entry_title, self.driver.accessory),
            self.driver.state.pincode,
            self.driver.accessory.xhm_uri(),
        )

    @callback
    def async_unpair(self) -> None:
        """Remove all pairings for an accessory so it can be repaired."""
        assert self.driver is not None

        state = self.driver.state
        for client_uuid in list(state.paired_clients):
            # We need to check again since removing a single client
            # can result in removing all the clients that the client
            # granted access to if it was an admin, otherwise
            # remove_paired_client can generate a KeyError
            if client_uuid in state.paired_clients:
                state.remove_paired_client(client_uuid)
        self.driver.async_persist()
        self.driver.async_update_advertisement()
        self._async_show_setup_message()

    @callback
    def _async_register_bridge(self) -> None:
        """Register the bridge as a device so homekit_controller and exclude it from discovery."""
        assert self.driver is not None
        dev_reg = device_registry.async_get(self.hass)
        formatted_mac = device_registry.format_mac(self.driver.state.mac)
        # Connections and identifiers are both used here.
        #
        # connections exists so homekit_controller can know the
        # virtual mac address of the bridge and know to not offer
        # it via discovery.
        #
        # identifiers is used as well since the virtual mac may change
        # because it will not survive manual pairing resets (deleting state file)
        # which we have trained users to do over the past few years
        # because this was the way you had to fix homekit when pairing
        # failed.
        #
        connection = (device_registry.CONNECTION_NETWORK_MAC, formatted_mac)
        identifier = (DOMAIN, self._entry_id, BRIDGE_SERIAL_NUMBER)
        self._async_purge_old_bridges(dev_reg, identifier, connection)
        is_accessory_mode = self._homekit_mode == HOMEKIT_MODE_ACCESSORY
        hk_mode_name = "Accessory" if is_accessory_mode else "Bridge"
        dev_reg.async_get_or_create(
            config_entry_id=self._entry_id,
            identifiers={
                identifier  # type: ignore[arg-type]
            },  # this needs to be migrated as a 2 item tuple at some point
            connections={connection},
            manufacturer=MANUFACTURER,
            name=accessory_friendly_name(self._entry_title, self.driver.accessory),
            model=f"HomeKit {hk_mode_name}",
            entry_type=device_registry.DeviceEntryType.SERVICE,
        )

    @callback
    def _async_purge_old_bridges(
        self,
        dev_reg: device_registry.DeviceRegistry,
        identifier: tuple[str, str, str],
        connection: tuple[str, str],
    ) -> None:
        """Purge bridges that exist from failed pairing or manual resets."""
        devices_to_purge = []
        for entry in dev_reg.devices.values():
            if self._entry_id in entry.config_entries and (
                identifier not in entry.identifiers  # type: ignore[comparison-overlap]
                or connection not in entry.connections
            ):
                devices_to_purge.append(entry.id)

        for device_id in devices_to_purge:
            dev_reg.async_remove_device(device_id)

    @callback
    def _async_create_single_accessory(
        self, entity_states: list[State]
    ) -> HomeAccessory | None:
        """Create a single HomeKit accessory (accessory mode)."""
        assert self.driver is not None

        if not entity_states:
            _LOGGER.error(
                "HomeKit %s cannot startup: entity not available: %s",
                self._name,
                self._filter.config,
            )
            return None
        state = entity_states[0]
        conf = self._config.get(state.entity_id, {}).copy()
        acc = get_accessory(self.hass, self.driver, state, STANDALONE_AID, conf)
        if acc is None:
            _LOGGER.error(
                "HomeKit %s cannot startup: entity not supported: %s",
                self._name,
                self._filter.config,
            )
        return acc

    async def _async_create_bridge_accessory(
        self, entity_states: Iterable[State]
    ) -> HomeAccessory:
        """Create a HomeKit bridge with accessories. (bridge mode)."""
        assert self.driver is not None

        self.bridge = HomeBridge(self.hass, self.driver, self._name)
        for state in entity_states:
            self.add_bridge_accessory(state)
        dev_reg = device_registry.async_get(self.hass)
        if self._devices:
            valid_device_ids = []
            for device_id in self._devices:
                if not dev_reg.async_get(device_id):
                    _LOGGER.warning(
                        "HomeKit %s cannot add device %s because it is missing from the device registry",
                        self._name,
                        device_id,
                    )
                else:
                    valid_device_ids.append(device_id)
            for device_id, device_triggers in (
                await device_automation.async_get_device_automations(
                    self.hass,
                    device_automation.DeviceAutomationType.TRIGGER,
                    valid_device_ids,
                )
            ).items():
                if device := dev_reg.async_get(device_id):
                    self.add_bridge_triggers_accessory(device, device_triggers)
        return self.bridge

    async def _async_create_accessories(self) -> bool:
        """Create the accessories."""
        assert self.driver is not None

        entity_states = await self.async_configure_accessories()
        if self._homekit_mode == HOMEKIT_MODE_ACCESSORY:
            acc = self._async_create_single_accessory(entity_states)
        else:
            acc = await self._async_create_bridge_accessory(entity_states)

        if acc is None:
            return False
        # No need to load/persist as we do it in setup
        self.driver.accessory = acc
        return True

    async def async_stop(self, *args: Any) -> None:
        """Stop the accessory driver."""
        if self.status != STATUS_RUNNING:
            return
        self.status = STATUS_STOPPED
        _LOGGER.debug("Driver stop for %s", self._name)
        if self.driver:
            await self.driver.async_stop()

    @callback
    def _async_configure_linked_sensors(
        self,
        ent_reg_ent: entity_registry.RegistryEntry,
        device_lookup: dict[str, dict[tuple[str, str | None], str]],
        state: State,
    ) -> None:
        if (
            ent_reg_ent is None
            or ent_reg_ent.device_id is None
            or ent_reg_ent.device_id not in device_lookup
            or (ent_reg_ent.device_class or ent_reg_ent.original_device_class)
            in (BinarySensorDeviceClass.BATTERY_CHARGING, SensorDeviceClass.BATTERY)
        ):
            return

        if ATTR_BATTERY_CHARGING not in state.attributes:
            battery_charging_binary_sensor_entity_id = device_lookup[
                ent_reg_ent.device_id
            ].get((BINARY_SENSOR_DOMAIN, BinarySensorDeviceClass.BATTERY_CHARGING))
            if battery_charging_binary_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_BATTERY_CHARGING_SENSOR,
                    battery_charging_binary_sensor_entity_id,
                )

        if ATTR_BATTERY_LEVEL not in state.attributes:
            battery_sensor_entity_id = device_lookup[ent_reg_ent.device_id].get(
                (SENSOR_DOMAIN, SensorDeviceClass.BATTERY)
            )
            if battery_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_BATTERY_SENSOR, battery_sensor_entity_id
                )

        if state.entity_id.startswith(f"{CAMERA_DOMAIN}."):
            motion_binary_sensor_entity_id = device_lookup[ent_reg_ent.device_id].get(
                (BINARY_SENSOR_DOMAIN, BinarySensorDeviceClass.MOTION)
            )
            if motion_binary_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_MOTION_SENSOR,
                    motion_binary_sensor_entity_id,
                )
            doorbell_binary_sensor_entity_id = device_lookup[ent_reg_ent.device_id].get(
                (BINARY_SENSOR_DOMAIN, BinarySensorDeviceClass.OCCUPANCY)
            )
            if doorbell_binary_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_DOORBELL_SENSOR,
                    doorbell_binary_sensor_entity_id,
                )

        if state.entity_id.startswith(f"{HUMIDIFIER_DOMAIN}."):
            current_humidity_sensor_entity_id = device_lookup[
                ent_reg_ent.device_id
            ].get((SENSOR_DOMAIN, SensorDeviceClass.HUMIDITY))
            if current_humidity_sensor_entity_id:
                self._config.setdefault(state.entity_id, {}).setdefault(
                    CONF_LINKED_HUMIDITY_SENSOR,
                    current_humidity_sensor_entity_id,
                )

    async def _async_set_device_info_attributes(
        self,
        ent_reg_ent: entity_registry.RegistryEntry,
        dev_reg: device_registry.DeviceRegistry,
        entity_id: str,
    ) -> None:
        """Set attributes that will be used for homekit device info."""
        ent_cfg = self._config.setdefault(entity_id, {})
        if ent_reg_ent.device_id:
            if dev_reg_ent := dev_reg.async_get(ent_reg_ent.device_id):
                self._fill_config_from_device_registry_entry(dev_reg_ent, ent_cfg)
        if ATTR_MANUFACTURER not in ent_cfg:
            try:
                integration = await async_get_integration(
                    self.hass, ent_reg_ent.platform
                )
                ent_cfg[ATTR_INTEGRATION] = integration.name
            except IntegrationNotFound:
                ent_cfg[ATTR_INTEGRATION] = ent_reg_ent.platform

    def _fill_config_from_device_registry_entry(
        self, device_entry: device_registry.DeviceEntry, config: dict[str, Any]
    ) -> None:
        """Populate a config dict from the registry."""
        if device_entry.manufacturer:
            config[ATTR_MANUFACTURER] = device_entry.manufacturer
        if device_entry.model:
            config[ATTR_MODEL] = device_entry.model
        if device_entry.sw_version:
            config[ATTR_SW_VERSION] = device_entry.sw_version
        if device_entry.hw_version:
            config[ATTR_HW_VERSION] = device_entry.hw_version
        if device_entry.config_entries:
            first_entry = list(device_entry.config_entries)[0]
            if entry := self.hass.config_entries.async_get_entry(first_entry):
                config[ATTR_INTEGRATION] = entry.domain


class HomeKitPairingQRView(HomeAssistantView):
    """Display the homekit pairing code at a protected url."""

    url = "/api/homekit/pairingqr"
    name = "api:homekit:pairingqr"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Retrieve the pairing QRCode image."""
        if not request.query_string:
            raise Unauthorized()
        entry_id, secret = request.query_string.split("-")

        if (
            entry_id not in request.app["hass"].data[DOMAIN]
            or secret
            != request.app["hass"].data[DOMAIN][entry_id][HOMEKIT_PAIRING_QR_SECRET]
        ):
            raise Unauthorized()
        return web.Response(
            body=request.app["hass"].data[DOMAIN][entry_id][HOMEKIT_PAIRING_QR],
            content_type="image/svg+xml",
        )
