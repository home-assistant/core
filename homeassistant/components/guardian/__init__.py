"""The Elexa Guardian integration."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]


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


@callback
def async_log_deprecated_service_call(
    hass: HomeAssistant,
    call: ServiceCall,
    alternate_service: str,
    alternate_target: str,
) -> None:
    """Log a warning about a deprecated service call."""
    LOGGER.warning(
        (
            'The "%s" service is deprecated and will be removed in a future version; '
            'use the "%s" service and pass it a target entity ID of "%s"'
        ),
        f"{call.domain}.{call.service}",
        alternate_service,
        alternate_target,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elexa Guardian from a config entry."""
    client = Client(entry.data[CONF_IP_ADDRESS], port=entry.data[CONF_PORT])

    # The valve controller's UDP-based API can't handle concurrent requests very well,
    # so we use a lock to ensure that only one API request is reaching it at a time:
    api_lock = asyncio.Lock()

    # Set up GuardianDataUpdateCoordinators for the valve controller:
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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def hydrate_with_entry_and_client(func: Callable) -> Callable:
        """Define a decorator to hydrate a method with args based on service call."""

        async def wrapper(call: ServiceCall) -> None:
            """Wrap the service function."""
            entry_id = async_get_entry_id_for_service_call(hass, call)
            client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
            entry = hass.config_entries.async_get_entry(entry_id)
            assert entry

            try:
                async with client:
                    await func(call, entry, client)
            except GuardianError as err:
                raise HomeAssistantError(
                    f"Error while executing {func.__name__}: {err}"
                ) from err

        return wrapper

    @hydrate_with_entry_and_client
    async def async_disable_ap(
        call: ServiceCall, entry: ConfigEntry, client: Client
    ) -> None:
        """Disable the onboard AP."""
        await client.wifi.disable_ap()

    @hydrate_with_entry_and_client
    async def async_enable_ap(
        call: ServiceCall, entry: ConfigEntry, client: Client
    ) -> None:
        """Enable the onboard AP."""
        await client.wifi.enable_ap()

    @hydrate_with_entry_and_client
    async def async_pair_sensor(
        call: ServiceCall, entry: ConfigEntry, client: Client
    ) -> None:
        """Add a new paired sensor."""
        paired_sensor_manager = hass.data[DOMAIN][entry.entry_id][
            DATA_PAIRED_SENSOR_MANAGER
        ]
        uid = call.data[CONF_UID]

        await client.sensor.pair_sensor(uid)
        await paired_sensor_manager.async_pair_sensor(uid)

    @hydrate_with_entry_and_client
    async def async_reboot(
        call: ServiceCall, entry: ConfigEntry, client: Client
    ) -> None:
        """Reboot the valve controller."""
        async_log_deprecated_service_call(
            hass,
            call,
            "button.press",
            f"button.guardian_valve_controller_{entry.data[CONF_UID]}_reboot",
        )
        await client.system.reboot()

    @hydrate_with_entry_and_client
    async def async_reset_valve_diagnostics(
        call: ServiceCall, entry: ConfigEntry, client: Client
    ) -> None:
        """Fully reset system motor diagnostics."""
        async_log_deprecated_service_call(
            hass,
            call,
            "button.press",
            f"button.guardian_valve_controller_{entry.data[CONF_UID]}_reset_valve_diagnostics",
        )
        await client.valve.reset()

    @hydrate_with_entry_and_client
    async def async_unpair_sensor(
        call: ServiceCall, entry: ConfigEntry, client: Client
    ) -> None:
        """Remove a paired sensor."""
        paired_sensor_manager = hass.data[DOMAIN][entry.entry_id][
            DATA_PAIRED_SENSOR_MANAGER
        ]
        uid = call.data[CONF_UID]

        await client.sensor.unpair_sensor(uid)
        await paired_sensor_manager.async_unpair_sensor(uid)

    @hydrate_with_entry_and_client
    async def async_upgrade_firmware(
        call: ServiceCall, entry: ConfigEntry, client: Client
    ) -> None:
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

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: GuardianDataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self.entity_description = description

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity.

        This should be extended by Guardian platforms.
        """

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self._async_update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._async_update_from_latest_data()


class PairedSensorEntity(GuardianEntity):
    """Define a Guardian paired sensor entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: GuardianDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)

        paired_sensor_uid = coordinator.data["uid"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, paired_sensor_uid)},
            manufacturer="Elexa",
            model=coordinator.data["codename"],
            name=f"Guardian paired sensor {paired_sensor_uid}",
            via_device=(DOMAIN, entry.data[CONF_UID]),
        )
        self._attr_unique_id = f"{paired_sensor_uid}_{description.key}"


@dataclass
class ValveControllerEntityDescriptionMixin:
    """Define an entity description mixin for valve controller entities."""

    api_category: str


@dataclass
class ValveControllerEntityDescription(
    EntityDescription, ValveControllerEntityDescriptionMixin
):
    """Describe a Guardian valve controller entity."""


class ValveControllerEntity(GuardianEntity):
    """Define a Guardian valve controller entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinators: dict[str, GuardianDataUpdateCoordinator],
        description: ValveControllerEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinators[description.api_category], description)

        self._diagnostics_coordinator = coordinators[API_SYSTEM_DIAGNOSTICS]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_UID])},
            manufacturer="Elexa",
            model=self._diagnostics_coordinator.data["firmware"],
            name=f"Guardian valve controller {entry.data[CONF_UID]}",
        )
        self._attr_unique_id = f"{entry.data[CONF_UID]}_{description.key}"
