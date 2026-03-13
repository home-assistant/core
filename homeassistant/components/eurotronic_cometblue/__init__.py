"""Comet Blue Bluetooth integration."""

from __future__ import annotations

from datetime import datetime
import logging
from uuid import UUID

from bleak.exc import BleakError
from eurotronic_cometblue_ha import AsyncCometBlue

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
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ALL_DAYS,
    CONF_RETRY_COUNT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_TIMEOUT_SECONDS,
    DOMAIN,
)
from .coordinator import CometBlueDataUpdateCoordinator
from .entity import CometBlueBluetoothEntity
from .utils import (
    SERVICE_DATETIME_SCHEMA,
    SERVICE_HOLIDAY_SCHEMA,
    SERVICE_SCHEDULE_SCHEMA,
)

DEFAULT_OPTIONS = {
    CONF_TIMEOUT: DEFAULT_TIMEOUT_SECONDS,
    CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT,
}
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
]
LOGGER = logging.getLogger(__name__)

type CometBlueConfigEntry = ConfigEntry[CometBlueDataUpdateCoordinator]


@callback
def _async_migrate_options_if_missing(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = dict(entry.data)

    if CONF_TIMEOUT not in entry.data or CONF_RETRY_COUNT not in entry.data:
        data[CONF_TIMEOUT] = entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT_SECONDS)
        data[CONF_RETRY_COUNT] = entry.data.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT)

        hass.config_entries.async_update_entry(entry, data=data)

    if CONF_PIN in entry.data and isinstance(entry.data[CONF_PIN], int):
        data[CONF_PIN] = f"{entry.data[CONF_PIN]:06d}"
        hass.config_entries.async_update_entry(entry, data=data)


async def async_setup_entry(hass: HomeAssistant, entry: CometBlueConfigEntry) -> bool:
    """Set up Eurotronic Comet Blue from a config entry."""

    _async_migrate_options_if_missing(hass, entry)

    address = entry.data[CONF_ADDRESS]

    ble_device = bluetooth.async_ble_device_from_address(hass, entry.data[CONF_ADDRESS])

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Couldn't find a nearby device for address: {entry.data[CONF_ADDRESS]}"
        )

    cometblue_device = AsyncCometBlue(
        device=ble_device,
        pin=int(entry.data[CONF_PIN]),
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
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Eurotronic Comet Blue entity services."""

    async def set_datetime(
        entity: CometBlueBluetoothEntity, service_call: ServiceCall
    ) -> None:
        """Service call to update the datetime on the device."""
        target_datetime = service_call.data.get("datetime") or datetime.now()
        await entity.coordinator.send_command(
            "set_datetime_async",
            {"date": target_datetime},
            service_call.service,
        )

    async def get_schedule(
        entity: CometBlueBluetoothEntity, service_call: ServiceCall
    ) -> ServiceResponse:
        """Service call to retrieve the schedule from the device."""
        return await entity.coordinator.send_command(
            "get_multiple_async",
            {"values": ["weekdays"]},
            service_call.service,
        )

    async def set_schedule(
        entity: CometBlueBluetoothEntity, service_call: ServiceCall
    ) -> None:
        """Service call to update the schedule on the device."""
        LOGGER.info(
            "Setting schedule for %s (%s)",
            entity.entity_id,
            entity.coordinator.device.device.address,
        )
        for day in CONF_ALL_DAYS:
            LOGGER.info(
                "%s - %s",
                day,
                service_call.data.get(day),
            )
        values = {
            day: {k: v.strftime("%H:%M") for k, v in sched.items()}
            for day, sched in service_call.data.items()
            if sched is not None and day in CONF_ALL_DAYS
        }
        await entity.coordinator.send_command(
            "set_weekdays_async",
            {"values": values},
            service_call.service,
        )

    async def set_holiday(
        entity: CometBlueBluetoothEntity, service_call: ServiceCall
    ) -> None:
        """Service call to update the holiday time on the device."""
        if (
            datetime(
                service_call.data["start"].year,
                service_call.data["start"].month,
                service_call.data["start"].day,
                service_call.data["start"].hour,
            )
            < datetime.now()
        ):
            raise ValueError("Start date (truncated to hour) must be in the future")

        LOGGER.info(
            "Setting holiday for %s (%s)",
            entity.entity_id,
            entity.coordinator.device.device.address,
        )
        await entity.coordinator.send_command(
            "set_holiday_async",
            {
                "number": 1,
                "values": {
                    "start": service_call.data["start"],
                    "end": service_call.data["end"],
                    "temperature": service_call.data["temperature"],
                },
            },
            service_call.service,
        )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_datetime",
        entity_domain="climate",
        schema=cv.make_entity_service_schema(SERVICE_DATETIME_SCHEMA),
        supports_response=SupportsResponse.NONE,
        func=set_datetime,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_schedule",
        entity_domain="climate",
        schema=None,
        supports_response=SupportsResponse.ONLY,
        func=get_schedule,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_schedule",
        entity_domain="climate",
        schema=cv.make_entity_service_schema(SERVICE_SCHEDULE_SCHEMA),
        supports_response=SupportsResponse.NONE,
        func=set_schedule,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_holiday",
        entity_domain="climate",
        schema=cv.make_entity_service_schema(SERVICE_HOLIDAY_SCHEMA),
        supports_response=SupportsResponse.NONE,
        func=set_holiday,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: CometBlueDataUpdateCoordinator = entry.runtime_data
        await coordinator.async_shutdown()

    return unload_ok
