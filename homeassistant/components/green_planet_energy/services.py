"""Services for Green Planet Energy integration."""

from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import DOMAIN
from .coordinator import GreenPlanetEnergyUpdateCoordinator

SERVICE_GET_PRICES = "get_prices"
ATTR_HOURS = "hours"

SERVICE_GET_PRICES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_HOURS): vol.All(
            vol.Coerce(float),
            vol.Range(min=0.25, max=24),
            lambda v: v
            if abs(v * 4 - round(v * 4)) < 1e-9
            else vol.Invalid("hours must be a multiple of 0.25 (15 minutes)"),
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
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_config_entry",
            )

        entry = entries[0]
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_loaded",
            )

        coordinator: GreenPlanetEnergyUpdateCoordinator = entry.runtime_data
        data = coordinator.data
        hours: float = call.data[ATTR_HOURS]

        now = dt_util.now()
        # Snap back to the start of the current 15-minute slot.
        slot_start = now.replace(
            minute=(now.minute // 15) * 15, second=0, microsecond=0
        )
        end_time = slot_start + timedelta(hours=hours)

        today_date = slot_start.date()
        tomorrow_date = (slot_start + timedelta(days=1)).date()

        slots: list[JsonValueType] = []
        current = slot_start
        while current < end_time:
            slot_end = current + timedelta(minutes=15)
            h = current.hour
            m = current.minute
            d = current.date()

            if d == today_date:
                key = f"gpe_price_{h:02d}_{m:02d}"
            elif d == tomorrow_date:
                key = f"gpe_price_{h:02d}_{m:02d}_tomorrow"
            else:
                # Beyond tomorrow — no data available, skip silently.
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
