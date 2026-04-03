"""Services for Green Planet Energy integration."""

from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.helpers.service import async_get_config_entry
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import DOMAIN

SERVICE_GET_PRICES = "get_prices"
ATTR_HOURS = "hours"


def _validate_hours(v: float) -> float:
    """Validate that hours is a multiple of 0.25 (15 minutes)."""
    if abs(v * 4 - round(v * 4)) >= 1e-9:
        raise vol.Invalid("hours must be a multiple of 0.25 (15 minutes)")
    return v


SERVICE_GET_PRICES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        vol.Required(ATTR_HOURS): vol.All(
            vol.Coerce(float),
            vol.Range(min=0.25, max=24),
            _validate_hours,
        ),
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Green Planet Energy."""

    async def get_prices(call: ServiceCall) -> ServiceResponse:
        """Return raw 15-minute-slot electricity prices for the next N hours.

        Prices are in EUR/kWh. Slots for which the API has no data yet (e.g.
        when the requested window extends beyond tomorrow) are silently omitted
        from the result.
        """
        entry = async_get_config_entry(hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID])
        data = entry.runtime_data.data
        hours: float = call.data[ATTR_HOURS]

        now = dt_util.now()
        slot_start = now.replace(
            minute=(now.minute // 15) * 15, second=0, microsecond=0
        )
        end_time = slot_start + timedelta(hours=hours)

        slots: list[JsonValueType] = []
        current = slot_start
        while current < end_time:
            slot_end = current + timedelta(minutes=15)
            h = current.hour
            m = current.minute

            if current.date() == slot_start.date():
                key = f"gpe_price_{h:02d}_{m:02d}"
            elif current.date() == (slot_start + timedelta(days=1)).date():
                key = f"gpe_price_{h:02d}_{m:02d}_tomorrow"
            else:
                current = slot_end
                continue

            if key in data:
                slots.append(
                    {
                        "start": current.isoformat(),
                        "end": slot_end.isoformat(),
                        "price": round(data[key] / 100, 6),
                    }
                )

            current = slot_end

        return {
            "prices": slots,
            "hours_requested": hours,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRICES,
        get_prices,
        schema=SERVICE_GET_PRICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
