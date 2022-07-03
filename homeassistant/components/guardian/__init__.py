"""The Elexa Guardian integration."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

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
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    API_SENSOR_PAIR_DUMP,
    API_SENSOR_PAIRED_SENSOR_STATUS,
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_VALVE_STATUS,
    API_WIFI_STATUS,
    CONF_UID,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DATA_COORDINATOR_PAIRED_SENSOR,
    DOMAIN,
    LOGGER,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
)
from .util import GuardianDataUpdateCoordinator

DATA_PAIRED_SENSOR_MANAGER = "paired_sensor_manager"

SERVICE_NAME_DISABLE_AP = "disable_ap"
SERVICE_NAME_ENABLE_AP = "enable_ap"
SERVICE_NAME_PAIR_SENSOR = "pair_sensor"
SERVICE_NAME_REBOOT = "reboot"
SERVICE_NAME_RESET_VALVE_DIAGNOSTICS = "reset_valve_diagnostics"
SERVICE_NAME_UNPAIR_SENSOR = "unpair_sensor"
SERVICE_NAME_UPGRADE_FIRMWARE = "upgrade_firmware"

SERVICES = (
    SERVICE_NAME_DISABLE_AP,
    SERVICE_NAME_ENABLE_AP,
    SERVICE_NAME_PAIR_SENSOR,
    SERVICE_NAME_REBOOT,
    SERVICE_NAME_RESET_VALVE_DIAGNOSTICS,
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


PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


@callback
def async_get_entry_id_for_service_call(hass: HomeAssistant, call: ServiceCall) -> str:
    """Get the entry ID related to a service call (by device ID)."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)

    if device_entry := device_registry.async_get(device_id):
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id in device_entry.config_entries:
                return entry.entry_id

    raise ValueError(f"No client for device ID: {device_id}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elexa Guardian from a config entry."""
    client = Client(entry.data[CONF_IP_ADDRESS], port=entry.data[CONF_PORT])

    # The valve controller's UDP-based API can't handle concurrent requests very well,
    # so we use a lock to ensure that only one API request is reaching it at a time:
    api_lock = asyncio.Lock()

    # Set up DataUpdateCoordinators for the valve controller:
    coordinators: dict[str, GuardianDataUpdateCoordinator] = {}
    init_valve_controller_tasks = []
    for api, api_coro in (
        (API_SENSOR_PAIR_DUMP, client.sensor.pair_dump),
        (API_SYSTEM_DIAGNOSTICS, client.system.diagnostics),
        (API_SYSTEM_ONBOARD_SENSOR_STATUS, client.system.onboard_sensor_status),
        (API_VALVE_STATUS, client.valve.status),
        (API_WIFI_STATUS, client.wifi.status),
    ):
        coordinator = coordinators[api] = GuardianDataUpdateCoordinator(
            hass,
            client=client,
            api_name=api,
            api_coro=api_coro,
            api_lock=api_lock,
            valve_controller_uid=entry.data[CONF_UID],
        )
        init_valve_controller_tasks.append(coordinator.async_refresh())

    await asyncio.gather(*init_valve_controller_tasks)

    # Set up an object to evaluate each batch of paired sensor UIDs and add/remove
    # devices as appropriate:
    paired_sensor_manager = PairedSensorManager(hass, entry, client, api_lock)
    await paired_sensor_manager.async_process_latest_paired_sensor_uids()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinators,
        DATA_COORDINATOR_PAIRED_SENSOR: {},
        DATA_PAIRED_SENSOR_MANAGER: paired_sensor_manager,
    }

    @callback
    def async_process_paired_sensor_uids() -> None:
        """Define a callback for when new paired sensor data is received."""
        hass.async_create_task(
            paired_sensor_manager.async_process_latest_paired_sensor_uids()
        )

    coordinators[API_SENSOR_PAIR_DUMP].async_add_listener(
        async_process_paired_sensor_uids
    )

    # Set up all of the Guardian entity platforms:
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    @callback
    def extract_client(func: Callable) -> Callable:
        """Define a decorator to get the correct client for a service call."""

        async def wrapper(call: ServiceCall) -> None:
            """Wrap the service function."""
            entry_id = async_get_entry_id_for_service_call(hass, call)
            client = hass.data[DOMAIN][entry_id][DATA_CLIENT]

            try:
                async with client:
                    await func(call, client)
            except GuardianError as err:
                raise HomeAssistantError(
                    f"Error while executing {func.__name__}: {err}"
                ) from err

        return wrapper

    @extract_client
    async def async_disable_ap(call: ServiceCall, client: Client) -> None:
        """Disable the onboard AP."""
        await client.wifi.disable_ap()

    @extract_client
    async def async_enable_ap(call: ServiceCall, client: Client) -> None:
        """Enable the onboard AP."""
        await client.wifi.enable_ap()

    @extract_client
    async def async_pair_sensor(call: ServiceCall, client: Client) -> None:
        """Add a new paired sensor."""
        entry_id = async_get_entry_id_for_service_call(hass, call)
        paired_sensor_manager = hass.data[DOMAIN][entry_id][DATA_PAIRED_SENSOR_MANAGER]
        uid = call.data[CONF_UID]

        await client.sensor.pair_sensor(uid)
        await paired_sensor_manager.async_pair_sensor(uid)

    @extract_client
    async def async_reboot(call: ServiceCall, client: Client) -> None:
        """Reboot the valve controller."""
        await client.system.reboot()

    @extract_client
    async def async_reset_valve_diagnostics(call: ServiceCall, client: Client) -> None:
        """Fully reset system motor diagnostics."""
        await client.valve.reset()

    @extract_client
    async def async_unpair_sensor(call: ServiceCall, client: Client) -> None:
        """Remove a paired sensor."""
        entry_id = async_get_entry_id_for_service_call(hass, call)
        paired_sensor_manager = hass.data[DOMAIN][entry_id][DATA_PAIRED_SENSOR_MANAGER]
        uid = call.data[CONF_UID]

        await client.sensor.unpair_sensor(uid)
        await paired_sensor_manager.async_unpair_sensor(uid)

    @extract_client
    async def async_upgrade_firmware(call: ServiceCall, client: Client) -> None:
        """Upgrade the device firmware."""
        await client.system.upgrade_firmware(
            url=call.data[CONF_URL],
            port=call.data[CONF_PORT],
            filename=call.data[CONF_FILENAME],
        )

    for service_name, schema, method in (
        (SERVICE_NAME_DISABLE_AP, SERVICE_BASE_SCHEMA, async_disable_ap),
        (SERVICE_NAME_ENABLE_AP, SERVICE_BASE_SCHEMA, async_enable_ap),
        (
            SERVICE_NAME_PAIR_SENSOR,
            SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA,
            async_pair_sensor,
        ),
        (SERVICE_NAME_REBOOT, SERVICE_BASE_SCHEMA, async_reboot),
        (
            SERVICE_NAME_RESET_VALVE_DIAGNOSTICS,
            SERVICE_BASE_SCHEMA,
            async_reset_valve_diagnostics,
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
    ) -> None:
        """Initialize."""
        self._api_lock = api_lock
        self._client = client
        self._entry = entry
        self._hass = hass
        self._paired_uids: set[str] = set()

    async def async_pair_sensor(self, uid: str) -> None:
        """Add a new paired sensor coordinator."""
        LOGGER.debug("Adding paired sensor: %s", uid)

        self._paired_uids.add(uid)

        coordinator = self._hass.data[DOMAIN][self._entry.entry_id][
            DATA_COORDINATOR_PAIRED_SENSOR
        ][uid] = GuardianDataUpdateCoordinator(
            self._hass,
            client=self._client,
            api_name=f"{API_SENSOR_PAIRED_SENSOR_STATUS}_{uid}",
            api_coro=lambda: cast(
                Awaitable, self._client.sensor.paired_sensor_status(uid)
            ),
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
            uids = set(
                self._hass.data[DOMAIN][self._entry.entry_id][DATA_COORDINATOR][
                    API_SENSOR_PAIR_DUMP
                ].data["paired_uids"]
            )
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
        self._hass.data[DOMAIN][self._entry.entry_id][
            DATA_COORDINATOR_PAIRED_SENSOR
        ].pop(uid)

        # Remove the paired sensor device from the device registry (which will
        # clean up entities and the entity registry):
        dev_reg = dr.async_get(self._hass)
        device = dev_reg.async_get_or_create(
            config_entry_id=self._entry.entry_id, identifiers={(DOMAIN, uid)}
        )
        dev_reg.async_remove_device(device.id)


class GuardianEntity(CoordinatorEntity):
    """Define a base Guardian entity."""

    def __init__(  # pylint: disable=super-init-not-called
        self, entry: ConfigEntry, description: EntityDescription
    ) -> None:
        """Initialize."""
        self._attr_device_info = DeviceInfo(manufacturer="Elexa")
        self._attr_extra_state_attributes = {}
        self._entry = entry
        self.entity_description = description

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity.

        This should be extended by Guardian platforms.
        """
        raise NotImplementedError


class PairedSensorEntity(GuardianEntity):
    """Define a Guardian paired sensor entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, description)

        paired_sensor_uid = coordinator.data["uid"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, paired_sensor_uid)},
            name=f"Guardian Paired Sensor {paired_sensor_uid}",
            via_device=(DOMAIN, entry.data[CONF_UID]),
        )
        self._attr_name = (
            f"Guardian Paired Sensor {paired_sensor_uid}: {description.name}"
        )
        self._attr_unique_id = f"{paired_sensor_uid}_{description.key}"
        self.coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        """Perform tasks when the entity is added."""
        self._async_update_from_latest_data()


class ValveControllerEntity(GuardianEntity):
    """Define a Guardian valve controller entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinators: dict[str, DataUpdateCoordinator],
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, description)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_UID])},
            model=coordinators[API_SYSTEM_DIAGNOSTICS].data["firmware"],
            name=f"Guardian Valve Controller {entry.data[CONF_UID]}",
        )
        self._attr_name = f"Guardian {entry.data[CONF_UID]}: {description.name}"
        self._attr_unique_id = f"{entry.data[CONF_UID]}_{description.key}"
        self.coordinators = coordinators

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return any(
            coordinator.last_update_success
            for coordinator in self.coordinators.values()
        )

    async def _async_continue_entity_setup(self) -> None:
        """Perform additional, internal tasks when the entity is about to be added.

        This should be extended by Guardian platforms.
        """
        raise NotImplementedError

    @callback
    def async_add_coordinator_update_listener(self, api: str) -> None:
        """Add a listener to a DataUpdateCoordinator based on the API referenced."""

        @callback
        def update() -> None:
            """Update the entity's state."""
            self._async_update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(self.coordinators[api].async_add_listener(update))

    async def async_added_to_hass(self) -> None:
        """Perform tasks when the entity is added."""
        await self._async_continue_entity_setup()
        self.async_add_coordinator_update_listener(API_SYSTEM_DIAGNOSTICS)
        self._async_update_from_latest_data()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        # Ignore manual update requests if the entity is disabled
        if not self.enabled:
            return

        refresh_tasks = [
            coordinator.async_request_refresh()
            for coordinator in self.coordinators.values()
        ]
        await asyncio.gather(*refresh_tasks)
