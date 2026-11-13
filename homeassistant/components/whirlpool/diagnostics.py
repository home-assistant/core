"""Diagnostics support for Whirlpool."""

from typing import Any

from whirlpool.appliance import Appliance

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import WhirlpoolConfigEntry

TO_REDACT = {
    "APPLIANCE_ID",
    "DEVICE_ID",
    "LOCATION_ID",
    "MACHINE_ID",
    "MAC_Address",
    "NEST_THERMOSTAT_ID",
    "SAID",
    "SERIAL",
    "SERIAL_NUMBER",
    "Serial",
    "SerialNumber",
    "UserId",
    "WifiMacAddress",
    "XCat_ApplianceInfoSetSerialNumber",
    "XCat_PersistentInfoMacAddress",
    "XCat_PersistentInfoSaid",
    "_id",
    "applianceId",
    "defaultClientId",
    "macaddress",
    "password",
    "said",
    "serial",
    "serialNumber",
    "serial_number",
    "thingArn",
    "thingId",
    "thingName",
    "token",
    "unique_id",
    "userId",
    "username",
    "wifiMacAddress",
    "wifi_mac",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    def get_appliance_diagnostics(appliance: Appliance) -> dict[str, Any]:
        return {
            "category": appliance.appliance_info.category,
            "model_number": appliance.appliance_info.model_number,
            "raw": appliance.get_raw_data(),
            "raw_info": appliance.appliance_info.raw_info,
        }

    appliances_manager = config_entry.runtime_data
    diagnostics_data = {
        category: [get_appliance_diagnostics(appliance) for appliance in appliances]
        for category, appliances in (
            ("washers", appliances_manager.washers),
            ("dryers", appliances_manager.dryers),
            ("aircons", appliances_manager.aircons),
            ("ovens", appliances_manager.ovens),
            ("microwaves", appliances_manager.microwaves),
            ("refrigerators", appliances_manager.refrigerators),
            ("unsupported", appliances_manager.unsupported_appliances),
        )
    }

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "appliances": async_redact_data(diagnostics_data, TO_REDACT),
    }
