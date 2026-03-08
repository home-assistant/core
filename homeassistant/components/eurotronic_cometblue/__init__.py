"""Comet Blue Bluetooth integration."""

from __future__ import annotations

from datetime import datetime
import logging
from uuid import UUID

from bleak.exc import BleakError
from eurotronic_cometblue_ha import AsyncCometBlue
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PIN, CONF_TIMEOUT, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_ALL_DAYS,
    CONF_RETRY_COUNT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_TIMEOUT_SECONDS,
    DOMAIN,
)
from .coordinator import CometBlueDataUpdateCoordinator
from .utils import (
    SERVICE_DATETIME_SCHEMA,
    SERVICE_ENTITY_SCHEMA,
    SERVICE_HOLIDAY_SCHEMA,
    SERVICE_SCHEDULE_SCHEMA,
    get_coordinator_for_service,
)

DEFAULT_OPTIONS = {
    CONF_TIMEOUT: DEFAULT_TIMEOUT_SECONDS,
    CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT,
}

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
]
LOGGER = logging.getLogger(__name__)


@callback
def _async_migrate_options_if_missing(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = dict(entry.data)

    if CONF_TIMEOUT not in entry.data or CONF_RETRY_COUNT not in entry.data:
        data[CONF_TIMEOUT] = entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT_SECONDS)
        data[CONF_RETRY_COUNT] = entry.data.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT)

        hass.config_entries.async_update_entry(entry, data=data)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gardena Bluetooth from a config entry."""

    _async_migrate_options_if_missing(hass, entry)

    address = entry.data[CONF_ADDRESS]

    ble_device = bluetooth.async_ble_device_from_address(hass, entry.data[CONF_ADDRESS])

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Couldn't find a nearby device for address: {entry.data[CONF_ADDRESS]}"
        )

    cometblue_device = AsyncCometBlue(
        device=ble_device,
        pin=entry.data[CONF_PIN],
        timeout=entry.data[CONF_TIMEOUT],
        retries=entry.data[CONF_RETRY_COUNT],
    )
    try:
        async with cometblue_device:
            if not cometblue_device.connected:
                raise ConfigEntryNotReady(
                    f"Failed to connect to '{cometblue_device.device.address}'"
                )
            device_info = DeviceInfo(
                identifiers={(DOMAIN, address)},
                name=f"{cometblue_device.device.name} {cometblue_device.device.address}",
                sw_version=bytes(
                    await cometblue_device.client.read_gatt_char(
                        UUID("00002a28-0000-1000-8000-00805f9b34fb")
                    )
                ).decode(),
                manufacturer=bytes(
                    await cometblue_device.client.read_gatt_char(
                        UUID("00002a29-0000-1000-8000-00805f9b34fb")
                    )
                ).decode(),
                model="Comet Blue",
            )
    except BleakError as ex:
        raise ConfigEntryNotReady(
            f"Failed to get device info from '{cometblue_device.device.address}'"
        ) from ex

    coordinator = CometBlueDataUpdateCoordinator(
        hass,
        entry,
        cometblue_device,
        device_info,
        retry_count=entry.data[CONF_RETRY_COUNT],
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def set_datetime(service_call: ServiceCall) -> None:
        """Service call to update the datetime on the device."""

        target_datetime = service_call.data.get("datetime") or datetime.now()

        for entity_id in service_call.data["entity_id"]:
            entity_coordinator = await get_coordinator_for_service(hass, entity_id)

            await entity_coordinator.send_command(
                "set_datetime_async",
                {"date": target_datetime},
                service_call.service,
            )

    async def get_schedule(
        service_call: ServiceCall,
    ) -> ServiceResponse:
        """Service call to retrieve the schedule from the device."""

        entity_coordinator = await get_coordinator_for_service(
            hass, service_call.data["entity_id"]
        )
        return await entity_coordinator.send_command(
            "get_multiple_async",
            {"values": ["weekdays"]},
            service_call.service,
        )

    async def set_schedule(service_call: ServiceCall) -> None:
        """Service call to update the schedule on the device."""

        data = service_call.data.copy()

        for entity_id in data.pop("entity_id", []):
            entity_coordinator = await get_coordinator_for_service(hass, entity_id)
            LOGGER.info(
                "Setting schedule for %s (%s)",
                entity_id,
                entity_coordinator.device.device.address,
            )
            for day in CONF_ALL_DAYS:
                LOGGER.info(
                    "%s - %s",
                    day,
                    service_call.data.get(day),
                )
            values = {
                day: {k: v.strftime("%H:%M") for k, v in sched.items()}
                for day, sched in data.items()
                if sched is not None
            }
            await entity_coordinator.send_command(
                "set_weekdays_async",
                {"values": values},
                service_call.service,
            )

    async def set_holiday(service_call: ServiceCall) -> None:
        """Service call to update the holiday time on the device."""

        data = service_call.data.copy()

        if (
            datetime(
                data["start"].year,
                data["start"].month,
                data["start"].day,
                data["start"].hour,
            )
            < datetime.now()
        ):
            raise ValueError("Start date (truncated to hour) must be in the future")

        for entity_id in data.pop("entity_id", []):
            entity_coordinator = await get_coordinator_for_service(hass, entity_id)
            LOGGER.info(
                "Setting holiday for %s (%s)",
                entity_id,
                entity_coordinator.device.device.address,
            )
            await entity_coordinator.send_command(
                "set_holiday_async",
                {
                    "number": 1,
                    "values": {
                        "start": data["start"],
                        "end": data["end"],
                        "temperature": data["temperature"],
                    },
                },
                service_call.service,
            )

    hass.services.async_register(
        DOMAIN,
        "set_datetime",
        set_datetime,
        schema=cv.make_entity_service_schema(SERVICE_DATETIME_SCHEMA),
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        "get_schedule",
        get_schedule,
        schema=vol.Schema(SERVICE_ENTITY_SCHEMA),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "set_schedule",
        set_schedule,
        schema=cv.make_entity_service_schema(SERVICE_SCHEDULE_SCHEMA),
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        "set_holiday",
        set_holiday,
        schema=cv.make_entity_service_schema(SERVICE_HOLIDAY_SCHEMA),
        supports_response=SupportsResponse.NONE,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: CometBlueDataUpdateCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        await coordinator.async_shutdown()

    return unload_ok
