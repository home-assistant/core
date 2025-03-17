"""All Util functions are listed here."""

import re
from typing import Any

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .exception import ConversionException

STORAGE_KEY = f"{DOMAIN}_selected_ac"
STORAGE_VERSION = 1


def get_HASS_ac_mode_from_ActronAir_ac_mode(actronair_ac_mode: str) -> HVACMode:
    """Convert Actron Air AC Mode to Home Assistant AC Mode."""
    match actronair_ac_mode:
        case "AUTO":
            return HVACMode.AUTO
        case "HEAT":
            return HVACMode.HEAT
        case "COOL":
            return HVACMode.COOL
        case "FAN":
            return HVACMode.FAN_ONLY
        case _:
            raise ConversionException(f"Unknown AC Mode - {actronair_ac_mode}")


def get_ActronAir_ac_mode_from_HASS_ac_mode(ac_mode: HVACMode) -> str:
    """Convert Home Assistant AC Mode to Actron Air AC Mode."""
    match ac_mode:
        case HVACMode.AUTO:
            return "AUTO"
        case HVACMode.HEAT:
            return "HEAT"
        case HVACMode.COOL:
            return "COOL"
        case HVACMode.FAN_ONLY:
            return "FAN"
        case _:
            raise ConversionException(f"Unknown AC Mode - {ac_mode}")


def get_HASS_fan_mode_from_ActronAir_fan_mode(actronair_fan_mode: str) -> Any:
    """Convert Actron Air AC Fan Mode to Home Assistant AC Fan Mode."""
    match actronair_fan_mode:
        case "HIGH":
            return FAN_HIGH
        case "MED":
            return FAN_MEDIUM
        case "LOW":
            return FAN_LOW
        case "AUTO":
            return FAN_AUTO
        case _:
            raise ConversionException(f"Unknown Fan Mode - {actronair_fan_mode}")


def get_ActronAir_fan_mode_from_HASS_fan_mode(fan_mode: str) -> str:
    """Convert Actron Air AC Fan Mode to Home Assistant AC Fan Mode."""
    match fan_mode:
        case "high":
            return "HIGH"
        case "medium":
            return "MED"
        case "low":
            return "LOW"
        case "auto":
            return "AUTO"
        case _:
            raise ConversionException(f"Unknown Fan Mode - {fan_mode}")


def get_serial_from_option_text(optionText: str) -> str | Any | None:
    """Util function to extract serial number from display text."""
    match = re.search(r"\((.*?)\)", optionText)
    return match.group(1) if match else None


async def getStoredData(hass: HomeAssistant, key: str) -> Any | None:
    """Retrieve stored data for the given key."""
    store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}
    return stored_data.get(key) if isinstance(stored_data, dict) else None


async def storeData(hass: HomeAssistant, key: str, value: str) -> None:
    """Store data (value) against the given key."""
    store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}
    stored_data[key] = value
    await store.async_save(stored_data)
