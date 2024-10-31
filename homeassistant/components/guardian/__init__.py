"""The Elexa Guardian integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from aioguardian import Client
from aioguardian.errors import GuardianError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_FILENAME,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_URL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    API_SENSOR_PAIR_DUMP,
    API_SENSOR_PAIRED_SENSOR_STATUS,
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_VALVE_STATUS,
    API_WIFI_STATUS,
    CONF_UID,
    DOMAIN,
    LOGGER,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
)
from .coordinator import GuardianDataUpdateCoordinator

DATA_PAIRED_SENSOR_MANAGER = "paired_sensor_manager"

SERVICE_NAME_PAIR_SENSOR = "pair_sensor"
SERVICE_NAME_UNPAIR_SENSOR = "unpair_sensor"
SERVICE_NAME_UPGRADE_FIRMWARE = "upgrade_firmware"

SERVICES = (
    SERVICE_NAME_PAIR_SENSOR,
    SERVICE_NAME_UNPAIR_SENSOR,
    SERVICE_NAME_UPGRADE_FIRMWARE,
)

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)

SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(CONF_UID): cv.string,
    }
)

SERVICE_UPGRADE_FIRMWARE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(CONF_URL): cv.url,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_FILENAME): cv.string,
    },
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]


@dataclass
class GuardianData:
    """Define an object to be stored in `hass.data`."""

    entry: ConfigEntry
    client: Client
    valve_controller_coordinators: dict[str, GuardianDataUpdateCoordinator]
    paired_sensor_manager: PairedSensorManager


@callback
def async_get_entry_id_for_service_call(hass: HomeAssistant, call: ServiceCall) -> str:
    """Get the entry ID related to a service call (by device ID)."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)

    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ValueError(f"Invalid Guardian device ID: {device_id}")

    for entry_id in device_entry.config_entries:
        if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN:
            return entry_id

    raise ValueError(f"No config entry for device ID: {device_id}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elexa Guardian from a config entry."""
    client = Client(entry.data[CONF_IP_ADDRESS], port=entry.data[CONF_PORT])

    # The valve controller's UDP-based API can't handle concurrent requests very well,
    # so we use a lock to ensure that only one API request is reaching it at a time:
    api_lock = asyncio.Lock()

    async def async_init_coordinator(
        coordinator: GuardianDataUpdateCoordinator,
    ) -> None:
        """Initialize a GuardianDataUpdateCoordinator."""
        await coordinator.async_initialize()
        await coordinator.async_config_entry_first_refresh()

    # Set up GuardianDataUpdateCoordinators for the valve controller:
    valve_controller_coordinators: dict[str, GuardianDataUpdateCoordinator] = {}
    init_valve_controller_tasks = []
    for api, api_coro in (
        (API_SENSOR_PAIR_DUMP, client.sensor.pair_dump),
        (API_SYSTEM_DIAGNOSTICS, client.system.diagnostics),
        (API_SYSTEM_ONBOARD_SENSOR_STATUS, client.system.onboard_sensor_status),
        (API_VALVE_STATUS, client.valve.status),
        (API_WIFI_STATUS, client.wifi.status),
    ):
        coordinator = valve_controller_coordinators[api] = (
            GuardianDataUpdateCoordinator(
                hass,
                entry=entry,
                client=client,
                api_name=api,
                api_coro=api_coro,
                api_lock=api_lock,
                valve_controller_uid=entry.data[CONF_UID],
            )
        )
        init_valve_controller_tasks.append(async_init_coordinator(coordinator))

    await asyncio.gather(*init_valve_controller_tasks)

    # Set up an object to evaluate each batch of paired sensor UIDs and add/remove
    # devices as appropriate:
    paired_sensor_manager = PairedSensorManager(
        hass,
        entry,
        client,
        api_lock,
        valve_controller_coordinators[API_SENSOR_PAIR_DUMP],
    )
    await paired_sensor_manager.async_initialize()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = GuardianData(
        entry=entry,
        client=client,
        valve_controller_coordinators=valve_controller_coordinators,
        paired_sensor_manager=paired_sensor_manager,
    )

    # Set up all of the Guardian entity platforms:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def call_with_data(
        func: Callable[[ServiceCall, GuardianData], Coroutine[Any, Any, None]],
    ) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
        """Hydrate a service call with the appropriate GuardianData object."""

        async def wrapper(call: ServiceCall) -> None:
            """Wrap the service function."""
            entry_id = async_get_entry_id_for_service_call(hass, call)
            data = hass.data[DOMAIN][entry_id]

            try:
                async with data.client:
                    await func(call, data)
            except GuardianError as err:
                raise HomeAssistantError(
                    f"Error while executing {func.__name__}: {err}"
                ) from err

        return wrapper

    @call_with_data
    async def async_pair_sensor(call: ServiceCall, data: GuardianData) -> None:
        """Add a new paired sensor."""
        uid = call.data[CONF_UID]
        await data.client.sensor.pair_sensor(uid)
        await data.paired_sensor_manager.async_pair_sensor(uid)

    @call_with_data
    async def async_unpair_sensor(call: ServiceCall, data: GuardianData) -> None:
        """Remove a paired sensor."""
        uid = call.data[CONF_UID]
        await data.client.sensor.unpair_sensor(uid)
        await data.paired_sensor_manager.async_unpair_sensor(uid)

    @call_with_data
    async def async_upgrade_firmware(call: ServiceCall, data: GuardianData) -> None:
        """Upgrade the device firmware."""
        await data.client.system.upgrade_firmware(
            url=call.data[CONF_URL],
            port=call.data[CONF_PORT],
            filename=call.data[CONF_FILENAME],
        )

    for service_name, schema, method in (
        (
            SERVICE_NAME_PAIR_SENSOR,
            SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA,
            async_pair_sensor,
        ),
        (
            SERVICE_NAME_UNPAIR_SENSOR,
            SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA,
            async_unpair_sensor,
        ),
        (
            SERVICE_NAME_UPGRADE_FIRMWARE,
            SERVICE_UPGRADE_FIRMWARE_SCHEMA,
            async_upgrade_firmware,
        ),
    ):
        if hass.services.has_service(DOMAIN, service_name):
            continue
        hass.services.async_register(DOMAIN, service_name, method, schema=schema)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        # If this is the last loaded instance of Guardian, deregister any services
        # defined during integration setup:
        for service_name in SERVICES:
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok


class PairedSensorManager:
    """Define an object that manages the addition/removal of paired sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: Client,
        api_lock: asyncio.Lock,
        sensor_pair_dump_coordinator: GuardianDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        self._api_lock = api_lock
        self._client = client
        self._entry = entry
        self._hass = hass
        self._paired_uids: set[str] = set()
        self._sensor_pair_dump_coordinator = sensor_pair_dump_coordinator
        self.coordinators: dict[str, GuardianDataUpdateCoordinator] = {}

    async def async_initialize(self) -> None:
        """Initialize the manager."""

        @callback
        def async_create_process_task() -> None:
            """Define a callback for when new paired sensor data is received."""
            self._hass.async_create_task(self.async_process_latest_paired_sensor_uids())

        self._entry.async_on_unload(
            self._sensor_pair_dump_coordinator.async_add_listener(
                async_create_process_task
            )
        )

    async def async_pair_sensor(self, uid: str) -> None:
        """Add a new paired sensor coordinator."""
        LOGGER.debug("Adding paired sensor: %s", uid)

        self._paired_uids.add(uid)

        coordinator = self.coordinators[uid] = GuardianDataUpdateCoordinator(
            self._hass,
            entry=self._entry,
            client=self._client,
            api_name=f"{API_SENSOR_PAIRED_SENSOR_STATUS}_{uid}",
            api_coro=lambda: self._client.sensor.paired_sensor_status(uid),
            api_lock=self._api_lock,
            valve_controller_uid=self._entry.data[CONF_UID],
        )
        await coordinator.async_request_refresh()

        async_dispatcher_send(
            self._hass,
            SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED.format(self._entry.data[CONF_UID]),
            uid,
        )

    async def async_process_latest_paired_sensor_uids(self) -> None:
        """Process a list of new UIDs."""
        try:
            uids = set(self._sensor_pair_dump_coordinator.data["paired_uids"])
        except KeyError:
            # Sometimes the paired_uids key can fail to exist; the user can't do anything
            # about it, so in this case, we quietly abort and return:
            return

        if uids == self._paired_uids:
            return

        old = self._paired_uids
        new = self._paired_uids = set(uids)

        tasks = [self.async_pair_sensor(uid) for uid in new.difference(old)]
        tasks += [self.async_unpair_sensor(uid) for uid in old.difference(new)]

        if tasks:
            await asyncio.gather(*tasks)

    async def async_unpair_sensor(self, uid: str) -> None:
        """Remove a paired sensor coordinator."""
        LOGGER.debug("Removing paired sensor: %s", uid)

        # Clear out objects related to this paired sensor:
        self._paired_uids.remove(uid)
        self.coordinators.pop(uid)

        # Remove the paired sensor device from the device registry (which will
        # clean up entities and the entity registry):
        dev_reg = dr.async_get(self._hass)
        device = dev_reg.async_get_or_create(
            config_entry_id=self._entry.entry_id, identifiers={(DOMAIN, uid)}
        )
        dev_reg.async_remove_device(device.id)
