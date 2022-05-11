"""The Raspberry Pi integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Raspberry Pi."""

    await hass.config_entries.flow.async_init(
        "rpi_power", context={"source": "onboarding"}
    )

    return True
