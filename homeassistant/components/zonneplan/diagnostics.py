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
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ZonneplanConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data

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
        },
        TO_REDACT,
    )
