"""Diagnostics support for the Zonneplan integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import ZonneplanConfigEntry

TO_REDACT = {
    CONF_EMAIL,
    CONF_TOKEN,
    "access_token",
    "refresh_token",
    "email",
    "first_name",
    "full_name",
    "initials",
    "street",
    "number",
    "addition",
    "zipcode",
    "city",
    "ean",
    "serial_number",
    "uuid",
    "external_contract_id",
    "identifier",
    "last_known_vehicle_uuid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ZonneplanConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.coordinator.data

    return async_redact_data(
        {
            "entry_data": dict(entry.data),
            "account": data.account.to_dict(),
            "connections": [
                connection.to_dict()
                for connection in data.account.connections
                if data.account.connections is not None and connection is not None
            ],
            "electricity_prices": (
                data.electricity_prices.to_dict() if data.electricity_prices else None
            ),
            "gas_prices": data.gas_prices.to_dict() if data.gas_prices else None,
            "electricity_usage": (
                data.electricity_usage.to_dict() if data.electricity_usage else None
            ),
            "gas_usage": data.gas_usage.to_dict() if data.gas_usage else None,
            "batteries": [
                battery_data.battery.contract.to_dict()
                for battery_data in entry.runtime_data.battery_coordinator.data.values()
            ],
            "battery_control_modes": [
                control_mode.to_dict()
                for control_mode in (
                    entry.runtime_data.battery_control_coordinator.data or {}
                ).values()
            ],
            "charge_points": [
                charge_point.to_dict()
                for charge_point in (
                    entry.runtime_data.charge_point_coordinator.data.values()
                )
            ],
        },
        TO_REDACT,
    )
