"""Diagnostics support for aWATTar."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import AwattarDataUpdateCoordinator
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: AwattarDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
        },
        "energy": {
            "current_hour_price": coordinator.data.energy[0].price_per_kWh,
            "next_hour_price": coordinator.data.energy[1].price_per_kWh,
            "average_price": coordinator.data.awattar.mean().price_per_kWh,
            "max_price": coordinator.data.awattar.max().price_per_kWh,
            "min_price": coordinator.data.awattar.min().price_per_kWh,
            "slot_2_hrs_start_time": coordinator.data.awattar.best_slot(
                2
            ).start_datetime,
            "slot_3_hrs_start_time": coordinator.data.awattar.best_slot(
                3
            ).start_datetime,
            "slot_4_hrs_start_time": coordinator.data.awattar.best_slot(
                4
            ).start_datetime,
            "slot_5_hrs_start_time": coordinator.data.awattar.best_slot(
                5
            ).start_datetime,
            "slot_6_hrs_start_time": coordinator.data.awattar.best_slot(
                6
            ).start_datetime,
            "slot_2_hrs_price": coordinator.data.awattar.best_slot(2).price_per_kWh,
            "slot_3_hrs_price": coordinator.data.awattar.best_slot(3).price_per_kWh,
            "slot_4_hrs_price": coordinator.data.awattar.best_slot(4).price_per_kWh,
            "slot_5_hrs_price": coordinator.data.awattar.best_slot(5).price_per_kWh,
            "slot_6_hrs_price": coordinator.data.awattar.best_slot(6).price_per_kWh,
        },
    }
