"""Home Assistant Anglian Water Diagnostics."""

from typing import Any

from pyanglianwater.enum import UsagesReadGranularity

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_ACCOUNT_NUMBER
from .coordinator import AnglianWaterConfigEntry

REDACTED_FIELDS = [
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_NUMBER,
    "refresh_token",
    "address",
    "formatted_address",
    "business_partner_number",
    "account_number",
    "sub_building_name",
    "house_number",
    "street",
    "city",
    "postcode",
    "move_in_date",
    "payment_type",
    "payment_arrangement_type",
    "serial",
    "serial_number",
    "meter_serial_number",
]

# For some reason AW store the meter serial number under 3 different keys.


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: AnglianWaterConfigEntry,
) -> dict[str, Any]:
    """Get diagnostics for a config entry."""
    return async_redact_data(
        {
            "config_entry": config_entry.data,
            "options": config_entry.options,
            "anglian_water": config_entry.runtime_data.api.to_dict(),
            "metering_data": await config_entry.runtime_data.api.get_usages(
                interval=UsagesReadGranularity.HOURLY, update_cache=False
            ),
        },
        REDACTED_FIELDS,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: AnglianWaterConfigEntry,
    device_entry: DeviceEntry,
) -> dict[str, Any]:
    """Get diagnostics for a device entry."""
    # At this point the device will always be registered with a serial number.
    # The API always returns a serial number for any type of meter.
    assert device_entry.serial_number
    smart_meter = config_entry.runtime_data.api.meters.get(device_entry.serial_number)
    assert smart_meter
    return async_redact_data(
        {
            "device_entry_id": device_entry.id,
            "meter": smart_meter.to_dict(),
        },
        REDACTED_FIELDS,
    )
