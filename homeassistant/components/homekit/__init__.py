"""Support for Apple HomeKit."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from copy import deepcopy
import ipaddress
import logging
import os
import socket
from typing import Any, cast

from aiohttp import web
from pyhap import util as pyhap_util
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
from homeassistant.components.device_automation.trigger import (
    async_validate_trigger_config,
)
from homeassistant.components.event import DOMAIN as EVENT_DOMAIN, EventDeviceClass
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.humidifier import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
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
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_RELOAD,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    HomeAssistant,
    ServiceCall,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    instance_id,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
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
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.util.async_ import create_eager_task

from . import (  # noqa: F401
    type_air_purifiers,
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
    CONF_LINKED_PM25_SENSOR,
    CONF_LINKED_TEMPERATURE_SENSOR,
    CONFIG_OPTIONS,
    DEFAULT_EXCLUDE_ACCESSORY_MODE,
    DEFAULT_HOMEKIT_MODE,
    DEFAULT_PORT,
    DOMAIN,
    HOMEKIT_MODE_ACCESSORY,
    HOMEKIT_MODES,
    MANUFACTURER,
    PERSIST_LOCK_DATA,
    SERVICE_HOMEKIT_RESET_ACCESSORY,
    SERVICE_HOMEKIT_UNPAIR,
    SHUTDOWN_TIMEOUT,
    SIGNAL_RELOAD_ENTITIES,
    TYPE_AIR_PURIFIER,
)
from .iidmanager import AccessoryIIDStorage
from .models import HomeKitConfigEntry, HomeKitEntryData
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
_HAS_IPV6 = hasattr(socket, "AF_INET6")
_DEFAULT_BIND = ["0.0.0.0", "::"] if _HAS_IPV6 else ["0.0.0.0"]


BATTERY_CHARGING_SENSOR = (
    BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass.BATTERY_CHARGING,
)
BATTERY_SENSOR = (SENSOR_DOMAIN, SensorDeviceClass.BATTERY)
MOTION_EVENT_SENSOR = (EVENT_DOMAIN, EventDeviceClass.MOTION)
MOTION_SENSOR = (BINARY_SENSOR_DOMAIN, BinarySensorDeviceClass.MOTION)
DOORBELL_EVENT_SENSOR = (EVENT_DOMAIN, EventDeviceClass.DOORBELL)
HUMIDITY_SENSOR = (SENSOR_DOMAIN, SensorDeviceClass.HUMIDITY)
TEMPERATURE_SENSOR = (SENSOR_DOMAIN, SensorDeviceClass.TEMPERATURE)
PM25_SENSOR = (SENSOR_DOMAIN, SensorDeviceClass.PM25)


def _has_all_unique_names_and_ports(
    bridges: list[dict[str, Any]],
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
            vol.Optional(CONF_ADVERTISE_IP): vol.All(
                cv.ensure_list, [ipaddress.ip_address], [cv.string]
            ),
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


@callback
def _async_update_entries_from_yaml(
    hass: HomeAssistant, config: ConfigType, start_import_flow: bool
) -> None:
    current_entries = hass.config_entries.async_entries(DOMAIN)
    entries_by_name, entries_by_port = _async_get_imported_entries_indices(
        current_entries
    )
    hk_config: list[dict[str, Any]] = config[DOMAIN]

    for index, conf in enumerate(hk_config):
        if _async_update_config_entry_from_yaml(
            hass, entries_by_name, entries_by_port, conf
        ):
            continue

        if start_import_flow:
            conf[CONF_ENTRY_INDEX] = index
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=conf,
                ),
                eager_start=True,
            )


def _async_all_homekit_instances(hass: HomeAssistant) -> list[HomeKit]:
    """All active HomeKit instances."""
    hk_data: HomeKitEntryData | None
    return [
        hk_data.homekit
        for entry in hass.config_entries.async_entries(DOMAIN)
        if (hk_data := getattr(entry, "runtime_data", None))
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
    hass.data[PERSIST_LOCK_DATA] = asyncio.Lock()

    # Initialize the loader before loading entries to ensure
    # there is no race where multiple entries try to load it
    # at the same time.
    await hass.async_add_executor_job(get_loader)

    _async_register_events_and_services(hass)
    if DOMAIN not in config:
        return True

    _async_update_entries_from_yaml(hass, config, start_import_flow=True)
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


async def async_setup_entry(hass: HomeAssistant, entry: HomeKitConfigEntry) -> bool:
    """Set up HomeKit from a config entry."""
    _async_import_options_from_data_if_missing(hass, entry)

    conf = entry.data
    options = entry.options

    name: str = conf[CONF_NAME]
    port: int = conf[CONF_PORT]
    # ip_address and advertise_ip are yaml only
    ip_address: str | list[str] | None = conf.get(CONF_IP_ADDRESS, _DEFAULT_BIND)
    advertise_ips: list[str]
    advertise_ips = conf.get(
        CONF_ADVERTISE_IP
    ) or await network.async_get_announce_addresses(hass)

    # exclude_accessory_mode is only used for config flow
    # to indicate that the config entry was setup after
    # we started creating config entries for entities that
    # to run in accessory mode and that we should never include
    # these entities on the bridge. For backwards compatibility
    # with users who have not migrated yet we do not do exclude
    # these entities by default as we cannot migrate automatically
    # since it requires a re-pairing.
    exclude_accessory_mode: bool = conf.get(
        CONF_EXCLUDE_ACCESSORY_MODE, DEFAULT_EXCLUDE_ACCESSORY_MODE
    )
    homekit_mode: str = options.get(CONF_HOMEKIT_MODE, DEFAULT_HOMEKIT_MODE)
    entity_config: dict[str, Any] = options.get(CONF_ENTITY_CONFIG, {}).copy()
    entity_filter: EntityFilter = FILTER_SCHEMA(options.get(CONF_FILTER, {}))
    devices: list[str] = options.get(CONF_DEVICES, [])

    homekit = HomeKit(
        hass,
        name,
        port,
        ip_address,
        entity_filter,
        exclude_accessory_mode,
        entity_config,
        homekit_mode,
        advertise_ips,
        entry.entry_id,
        entry.title,
        devices=devices,
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, homekit.async_stop)
    )

    entry_data = HomeKitEntryData(
        homekit=homekit, pairing_qr=None, pairing_qr_secret=None
    )
    entry.runtime_data = entry_data

    async def _async_start_homekit(hass: HomeAssistant) -> None:
        await homekit.async_start()

    entry.async_on_unload(async_at_started(hass, _async_start_homekit))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: HomeKitConfigEntry
) -> None:
    """Handle options update."""
    if entry.source == SOURCE_IMPORT:
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HomeKitConfigEntry) -> bool:
    """Unload a config entry."""
    async_dismiss_setup_message(hass, entry.entry_id)
    entry_data = entry.runtime_data
    homekit = entry_data.homekit

    if homekit.status == STATUS_RUNNING:
        await homekit.async_stop()

    logged_shutdown_wait = False
    for _ in range(SHUTDOWN_TIMEOUT):
        if async_port_is_available(entry.data[CONF_PORT]):
            break

        if not logged_shutdown_wait:
            _LOGGER.debug("Waiting for the HomeKit server to shutdown")
            logged_shutdown_wait = True

        await asyncio.sleep(PORT_CLEANUP_CHECK_INTERVAL_SECS)

    return True


async def async_remove_entry(hass: HomeAssistant, entry: HomeKitConfigEntry) -> None:
    """Remove a config entry."""
    await hass.async_add_executor_job(
        remove_state_files_for_entry_id, hass, entry.entry_id
    )


@callback
def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: HomeKitConfigEntry
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
        dev_reg = dr.async_get(hass)
        for device_id in referenced.referenced_devices:
            if not (dev_reg_ent := dev_reg.async_get(device_id)):
                raise HomeAssistantError(f"No device found for device id: {device_id}")
            macs = [
                cval
                for ctype, cval in dev_reg_ent.connections
                if ctype == dr.CONNECTION_NETWORK_MAC
            ]
            matching_instances = [
                homekit
                for homekit in _async_all_homekit_instances(hass)
                if homekit.driver and dr.format_mac(homekit.driver.state.mac) in macs
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
        _async_update_entries_from_yaml(hass, config, start_import_flow=False)
        await asyncio.gather(
            *(
                create_eager_task(hass.config_entries.async_reload(entry.entry_id))
                for entry in hass.config_entries.async_entries(DOMAIN)
            )
        )

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
        ip_address: list[str] | str | None,
        entity_filter: EntityFilter,
        exclude_accessory_mode: bool,
        entity_config: dict[str, Any],
        homekit_mode: str,
        advertise_ips: list[str],
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
        self._config: defaultdict[str, dict[str, Any]] = defaultdict(
            dict, entity_config
        )
        self._exclude_accessory_mode = exclude_accessory_mode
        self._advertise_ips = advertise_ips
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
        self._cancel_reload_dispatcher: CALLBACK_TYPE | None = None

    def setup(self, async_zeroconf_instance: AsyncZeroconf, uuid: str) -> bool:
        """Set up bridge and accessory driver.

        Returns True if data was loaded from disk

        Returns False if the persistent data was not loaded
        """
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
            advertised_address=self._advertise_ips,
            async_zeroconf_instance=async_zeroconf_instance,
            zeroconf_server=f"{uuid}-hap.local.",
            loader=get_loader(),
            iid_storage=self.iid_storage,
        )
        # If we do not load the mac address will be wrong
        # as pyhap uses a random one until state is restored
        if os.path.exists(persist_file):
            self.driver.load()
            return True

        # If there is no persist file, we need to generate a mac
        self.driver.state.mac = pyhap_util.generate_mac()
        return False

    async def async_reset_accessories(self, entity_ids: Iterable[str]) -> None:
        """Reset the accessory to load the latest configuration."""
        _LOGGER.debug("Resetting accessories: %s", entity_ids)
        async with self._reset_lock:
            if not self.bridge:
                # For accessory mode reset and reload are the same
                await self._async_reload_accessories_in_accessory_mode(entity_ids)
                return
            await self._async_reset_accessories_in_bridge_mode(entity_ids)

    async def async_reload_accessories(self, entity_ids: Iterable[str]) -> None:
        """Reload the accessory to load the latest configuration."""
        _LOGGER.debug("Reloading accessories: %s", entity_ids)
        async with self._reset_lock:
            if not self.bridge:
                await self._async_reload_accessories_in_accessory_mode(entity_ids)
                return
            await self._async_reload_accessories_in_bridge_mode(entity_ids)

    @callback
    def _async_shutdown_accessory(self, accessory: HomeAccessory) -> None:
        """Shutdown an accessory."""
        assert self.driver is not None
        accessory.async_stop()
        # Deallocate the IIDs for the accessory
        iid_manager = accessory.iid_manager
        services: list[Service] = accessory.services
        for service in services:
            iid_manager.remove_obj(service)
            characteristics: list[Characteristic] = service.characteristics
            for char in characteristics:
                iid_manager.remove_obj(char)

    async def _async_reload_accessories_in_accessory_mode(
        self, entity_ids: Iterable[str]
    ) -> None:
        """Reset accessories in accessory mode."""
        assert self.driver is not None

        acc = cast(HomeAccessory, self.driver.accessory)
        if acc.entity_id not in entity_ids:
            return
        if not (state := self.hass.states.get(acc.entity_id)):
            _LOGGER.warning(
                "The underlying entity %s disappeared during reload", acc.entity_id
            )
            return
        self._async_shutdown_accessory(acc)
        if new_acc := self._async_create_single_accessory([state]):
            self.driver.accessory = new_acc
            new_acc.run()
            self._async_update_accessories_hash()

    def _async_remove_accessories_by_entity_id(
        self, entity_ids: Iterable[str]
    ) -> list[str]:
        """Remove accessories by entity id."""
        assert self.aid_storage is not None
        assert self.bridge is not None
        removed: list[str] = []
        acc: HomeAccessory | None
        for entity_id in entity_ids:
            aid = self.aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
            if aid not in self.bridge.accessories:
                continue
            if acc := self.async_remove_bridge_accessory(aid):
                self._async_shutdown_accessory(acc)
                removed.append(entity_id)
        return removed

    async def _async_reset_accessories_in_bridge_mode(
        self, entity_ids: Iterable[str]
    ) -> None:
        """Reset accessories in bridge mode."""
        if not (removed := self._async_remove_accessories_by_entity_id(entity_ids)):
            _LOGGER.debug("No accessories to reset in bridge mode for: %s", entity_ids)
            return
        # With a reset, we need to remove the accessories,
        # and force config change so iCloud deletes them from
        # the database.
        assert self.driver is not None
        self._async_update_accessories_hash()
        await asyncio.sleep(_HOMEKIT_CONFIG_UPDATE_TIME)
        await self._async_recreate_removed_accessories_in_bridge_mode(removed)

    async def _async_reload_accessories_in_bridge_mode(
        self, entity_ids: Iterable[str]
    ) -> None:
        """Reload accessories in bridge mode."""
        removed = self._async_remove_accessories_by_entity_id(entity_ids)
        await self._async_recreate_removed_accessories_in_bridge_mode(removed)

    async def _async_recreate_removed_accessories_in_bridge_mode(
        self, removed: list[str]
    ) -> None:
        """Recreate removed accessories in bridge mode."""
        for entity_id in removed:
            if not (state := self.hass.states.get(entity_id)):
                _LOGGER.warning(
                    "The underlying entity %s disappeared during reload", entity_id
                )
                continue
            if acc := self.add_bridge_accessory(state):
                acc.run()
        self._async_update_accessories_hash()

    @callback
    def _async_update_accessories_hash(self) -> bool:
        """Update the accessories hash."""
        assert self.driver is not None
        driver = self.driver
        old_hash = driver.state.accessories_hash
        new_hash = driver.accessories_hash
        if driver.state.set_accessories_hash(new_hash):
            _LOGGER.debug(
                "Updating HomeKit accessories hash from %s -> %s", old_hash, new_hash
            )
            driver.async_persist()
            driver.async_update_advertisement()
            return True
        _LOGGER.debug("HomeKit accessories hash is unchanged: %s", new_hash)
        return False

    def add_bridge_accessory(self, state: State) -> HomeAccessory | None:
        """Try adding accessory to bridge if configured beforehand."""
        assert self.driver is not None

        if self._would_exceed_max_devices(state.entity_id):
            return None

        if state_needs_accessory_mode(state):
            if self._exclude_accessory_mode:
                return None
            _LOGGER.warning(
                (
                    "The bridge %s has entity %s. For best performance, "
                    "and to prevent unexpected unavailability, create and "
                    "pair a separate HomeKit instance in accessory mode for "
                    "this entity"
                ),
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
        except Exception:
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
                (
                    "Cannot add %s as this would exceed the %d device limit. Consider"
                    " using the filter option"
                ),
                name,
                MAX_DEVICES,
            )
            return True
        return False

    async def add_bridge_triggers_accessory(
        self, device: dr.DeviceEntry, device_triggers: list[dict[str, Any]]
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
        trigger_accessory = DeviceTriggerAccessory(
            self.hass,
            self.driver,
            device.name,
            None,
            aid,
            config,
            device_id=device.id,
            device_triggers=device_triggers,
        )
        await trigger_accessory.async_attach()
        self.bridge.add_accessory(trigger_accessory)

    @callback
    def async_remove_bridge_accessory(self, aid: int) -> HomeAccessory | None:
        """Try adding accessory to bridge if configured beforehand."""
        assert self.bridge is not None
        if acc := self.bridge.accessories.pop(aid, None):
            return cast(HomeAccessory, acc)
        return None

    async def async_configure_accessories(self) -> list[State]:
        """Configure accessories for the included states."""
        dev_reg = dr.async_get(self.hass)
        ent_reg = er.async_get(self.hass)
        device_lookup: dict[str, dict[tuple[str, str | None], str]] = {}
        entity_states: list[State] = []
        entity_filter = self._filter.get_filter()
        entries = ent_reg.entities
        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            if not entity_filter(entity_id):
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
                if device_id := ent_reg_ent.device_id:
                    if device_id not in device_lookup:
                        device_lookup[device_id] = {
                            (
                                entry.domain,
                                entry.device_class or entry.original_device_class,
                            ): entry.entity_id
                            for entry in entries.get_entries_for_device_id(device_id)
                        }
                    self._async_configure_linked_sensors(
                        ent_reg_ent, device_lookup[device_id], state
                    )

            entity_states.append(state)

        return entity_states

    async def async_start(self, *args: Any) -> None:
        """Load storage and start."""
        if self.status != STATUS_READY:
            return
        self.status = STATUS_WAIT
        self._cancel_reload_dispatcher = async_dispatcher_connect(
            self.hass,
            SIGNAL_RELOAD_ENTITIES.format(self._entry_id),
            self.async_reload_accessories,
        )
        async_zc_instance = await zeroconf.async_get_async_instance(self.hass)
        uuid = await instance_id.async_get(self.hass)
        self.aid_storage = AccessoryAidStorage(self.hass, self._entry_id)
        self.iid_storage = AccessoryIIDStorage(self.hass, self._entry_id)
        # Avoid gather here since it will be I/O bound anyways
        await self.aid_storage.async_initialize()
        await self.iid_storage.async_initialize()
        loaded_from_disk = await self.hass.async_add_executor_job(
            self.setup, async_zc_instance, uuid
        )
        assert self.driver is not None

        if not await self._async_create_accessories():
            return
        self._async_register_bridge()
        _LOGGER.debug("Driver start for %s", self._name)
        await self.driver.async_start()
        if not loaded_from_disk:
            # If the state was not loaded from disk, it means this is the
            # first time the bridge is ever starting up. In this case, we
            # need to make sure its persisted to disk.
            async with self.hass.data[PERSIST_LOCK_DATA]:
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
        dev_reg = dr.async_get(self.hass)
        formatted_mac = dr.format_mac(self.driver.state.mac)
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
        connection = (dr.CONNECTION_NETWORK_MAC, formatted_mac)
        identifier = (DOMAIN, self._entry_id, BRIDGE_SERIAL_NUMBER)
        self._async_purge_old_bridges(dev_reg, identifier, connection)
        accessory_type = type(self.driver.accessory).__name__
        dev_reg.async_get_or_create(
            config_entry_id=self._entry_id,
            identifiers={
                identifier  # type: ignore[arg-type]
            },  # this needs to be migrated as a 2 item tuple at some point
            connections={connection},
            manufacturer=MANUFACTURER,
            name=accessory_friendly_name(self._entry_title, self.driver.accessory),
            model=accessory_type,
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @callback
    def _async_purge_old_bridges(
        self,
        dev_reg: dr.DeviceRegistry,
        identifier: tuple[str, str, str],
        connection: tuple[str, str],
    ) -> None:
        """Purge bridges that exist from failed pairing or manual resets."""
        devices_to_purge = [
            entry.id
            for entry in dev_reg.devices.get_devices_for_config_entry_id(self._entry_id)
            if (
                identifier not in entry.identifiers  # type: ignore[comparison-overlap]
                or connection not in entry.connections
            )
        ]

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
        if self._devices:
            await self._async_add_trigger_accessories()
        return self.bridge

    async def _async_add_trigger_accessories(self) -> None:
        """Add devices with triggers to the bridge."""
        dev_reg = dr.async_get(self.hass)
        valid_device_ids = []
        for device_id in self._devices:
            if not dev_reg.async_get(device_id):
                _LOGGER.warning(
                    (
                        "HomeKit %s cannot add device %s because it is missing from the"
                        " device registry"
                    ),
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
            device = dev_reg.async_get(device_id)
            assert device is not None
            valid_device_triggers: list[dict[str, Any]] = []
            for trigger in device_triggers:
                try:
                    await async_validate_trigger_config(self.hass, trigger)
                except vol.Invalid as ex:
                    _LOGGER.debug(
                        (
                            "%s: cannot add unsupported trigger %s because it requires"
                            " additional inputs which are not supported by HomeKit: %s"
                        ),
                        self._name,
                        trigger,
                        ex,
                    )
                    continue
                valid_device_triggers.append(trigger)
            await self.add_bridge_triggers_accessory(device, valid_device_triggers)

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
        async with self._reset_lock:
            self.status = STATUS_STOPPED
            assert self._cancel_reload_dispatcher is not None
            self._cancel_reload_dispatcher()
            _LOGGER.debug("Driver stop for %s", self._name)
            if self.driver:
                await self.driver.async_stop()

    @callback
    def _async_configure_linked_sensors(
        self,
        ent_reg_ent: er.RegistryEntry,
        lookup: dict[tuple[str, str | None], str],
        state: State,
    ) -> None:
        if (ent_reg_ent.device_class or ent_reg_ent.original_device_class) in (
            BinarySensorDeviceClass.BATTERY_CHARGING,
            SensorDeviceClass.BATTERY,
        ):
            return

        domain = state.domain
        attributes = state.attributes
        config = self._config
        entity_id = state.entity_id

        if ATTR_BATTERY_CHARGING not in attributes and (
            battery_charging_binary_sensor_entity_id := lookup.get(
                BATTERY_CHARGING_SENSOR
            )
        ):
            config[entity_id].setdefault(
                CONF_LINKED_BATTERY_CHARGING_SENSOR,
                battery_charging_binary_sensor_entity_id,
            )

        if ATTR_BATTERY_LEVEL not in attributes and (
            battery_sensor_entity_id := lookup.get(BATTERY_SENSOR)
        ):
            config[entity_id].setdefault(
                CONF_LINKED_BATTERY_SENSOR, battery_sensor_entity_id
            )

        if domain == CAMERA_DOMAIN:
            if motion_event_entity_id := lookup.get(MOTION_EVENT_SENSOR):
                config[entity_id].setdefault(
                    CONF_LINKED_MOTION_SENSOR, motion_event_entity_id
                )
            elif motion_binary_sensor_entity_id := lookup.get(MOTION_SENSOR):
                config[entity_id].setdefault(
                    CONF_LINKED_MOTION_SENSOR, motion_binary_sensor_entity_id
                )

        if domain in (CAMERA_DOMAIN, LOCK_DOMAIN):
            if doorbell_event_entity_id := lookup.get(DOORBELL_EVENT_SENSOR):
                config[entity_id].setdefault(
                    CONF_LINKED_DOORBELL_SENSOR, doorbell_event_entity_id
                )

        if domain == FAN_DOMAIN:
            if current_humidity_sensor_entity_id := lookup.get(HUMIDITY_SENSOR):
                config[entity_id].setdefault(
                    CONF_LINKED_HUMIDITY_SENSOR, current_humidity_sensor_entity_id
                )
            if current_pm25_sensor_entity_id := lookup.get(PM25_SENSOR):
                config[entity_id].setdefault(CONF_TYPE, TYPE_AIR_PURIFIER)
                config[entity_id].setdefault(
                    CONF_LINKED_PM25_SENSOR, current_pm25_sensor_entity_id
                )
            if current_temperature_sensor_entity_id := lookup.get(TEMPERATURE_SENSOR):
                config[entity_id].setdefault(
                    CONF_LINKED_TEMPERATURE_SENSOR, current_temperature_sensor_entity_id
                )

        if domain == HUMIDIFIER_DOMAIN and (
            current_humidity_sensor_entity_id := lookup.get(HUMIDITY_SENSOR)
        ):
            config[entity_id].setdefault(
                CONF_LINKED_HUMIDITY_SENSOR, current_humidity_sensor_entity_id
            )

    async def _async_set_device_info_attributes(
        self,
        ent_reg_ent: er.RegistryEntry,
        dev_reg: dr.DeviceRegistry,
        entity_id: str,
    ) -> None:
        """Set attributes that will be used for homekit device info."""
        ent_cfg = self._config[entity_id]
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
        self, device_entry: dr.DeviceEntry, config: dict[str, Any]
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
            raise Unauthorized
        entry_id, secret = request.query_string.split("-")
        hass = request.app[KEY_HASS]
        entry_data: HomeKitEntryData | None
        if (
            not (entry := hass.config_entries.async_get_entry(entry_id))
            or not (entry_data := getattr(entry, "runtime_data", None))
            or not secret
            or not entry_data.pairing_qr_secret
            or secret != entry_data.pairing_qr_secret
        ):
            raise Unauthorized
        return web.Response(
            body=entry_data.pairing_qr,
            content_type="image/svg+xml",
        )
