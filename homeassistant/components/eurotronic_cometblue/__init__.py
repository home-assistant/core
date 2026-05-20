"""Comet Blue Bluetooth integration."""

from datetime import datetime
import logging

from bleak.exc import BleakError
from eurotronic_cometblue_ha import AsyncCometBlue
import voluptuous as vol

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PIN, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ALL_DAYS,
    CONF_DELETE,
    CONF_END,
    CONF_START,
    CONF_TEMPERATURE,
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
)
from .coordinator import CometBlueConfigEntry, CometBlueDataUpdateCoordinator
from .entity import CometBlueBluetoothEntity
from .utils import (
    valid_cometblue_schedule_keys,
    validate_cometblue_schedule,
    validate_half_precision,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
]
LOGGER = logging.getLogger(__name__)


SCHEDULE_DAY_SCHEMA = vol.All(
    {
        vol.Optional(CONF_DELETE): cv.boolean,
        **{vol.Optional(item): cv.time for item in valid_cometblue_schedule_keys()},
    },
    validate_cometblue_schedule,
)
SERVICE_SCHEDULE_SCHEMA = {
    vol.Optional(day): SCHEDULE_DAY_SCHEMA for day in CONF_ALL_DAYS
}
SERVICE_HOLIDAY_SCHEMA = {
    vol.Required(CONF_START): cv.datetime,
    vol.Required(CONF_END): cv.datetime,
    vol.Required(CONF_TEMPERATURE): vol.All(
        vol.Coerce(float),
        vol.Range(min=MIN_TEMP, max=MAX_TEMP),
        validate_half_precision,
    ),
}


async def async_setup_entry(hass: HomeAssistant, entry: CometBlueConfigEntry) -> bool:
    """Set up Eurotronic Comet Blue from a config entry."""

    address = entry.data[CONF_ADDRESS]

    ble_device = async_ble_device_from_address(hass, entry.data[CONF_ADDRESS])

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Couldn't find a nearby device for address: {entry.data[CONF_ADDRESS]}"
        )

    cometblue_device = AsyncCometBlue(
        device=ble_device,
        pin=int(entry.data[CONF_PIN]),
    )
    try:
        async with cometblue_device:
            ble_device_info = await cometblue_device.get_device_info_async()
            try:
                # Device only returns battery level if PIN is correct
                await cometblue_device.get_battery_async()
            except TimeoutError as ex:
                # This likely means PIN was incorrect on Linux and ESPHome backends
                raise ConfigEntryError(
                    "Failed to read battery level, likely due to incorrect PIN"
                ) from ex
    except BleakError as ex:
        raise ConfigEntryNotReady(
            f"Failed to get device info from '{cometblue_device.device.address}'"
        ) from ex

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        name=f"{ble_device_info['model']} {cometblue_device.device.address}",
        manufacturer=ble_device_info["manufacturer"],
        model=ble_device_info["model"],
        sw_version=ble_device_info["version"],
    )

    coordinator = CometBlueDataUpdateCoordinator(
        hass,
        entry,
        cometblue_device,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Eurotronic Comet Blue entity services."""

    async def get_schedule(
        entity: CometBlueBluetoothEntity, service_call: ServiceCall
    ) -> ServiceResponse:
        """Service call to retrieve the schedule from the device."""
        return await entity.coordinator.send_command(
            entity.coordinator.device.get_multiple_async,
            {"values": ["weekdays"]},
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
            entity.coordinator.device.set_weekdays_async,
            {"values": values},
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
            entity.coordinator.device.set_holiday_async,
            {
                "number": 1,
                "values": {
                    "start": service_call.data["start"],
                    "end": service_call.data["end"],
                    "temperature": service_call.data["temperature"],
                },
            },
        )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_schedule",
        entity_domain=CLIMATE_DOMAIN,
        schema=None,
        supports_response=SupportsResponse.ONLY,
        func=get_schedule,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_schedule",
        entity_domain=CLIMATE_DOMAIN,
        schema=cv.make_entity_service_schema(SERVICE_SCHEDULE_SCHEMA),
        supports_response=SupportsResponse.NONE,
        func=set_schedule,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_holiday",
        entity_domain=CLIMATE_DOMAIN,
        schema=cv.make_entity_service_schema(SERVICE_HOLIDAY_SCHEMA),
        supports_response=SupportsResponse.NONE,
        func=set_holiday,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
