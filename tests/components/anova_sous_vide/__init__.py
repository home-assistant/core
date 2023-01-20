"""Tests for the Anova Sous Vide integration."""
from __future__ import annotations

from anova_wifi import AnovaPrecisionCookerBinarySensor, AnovaPrecisionCookerSensor

from homeassistant.components.anova_sous_vide.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_ID = "abc123def"

CONF_INPUT = {"device_id": DEVICE_ID}

ONLINE_UPDATE = {
    "sensors": {
        AnovaPrecisionCookerSensor.COOK_TIME: 0,
        AnovaPrecisionCookerSensor.MODE: "Low water",
        AnovaPrecisionCookerSensor.STATE: "No state",
        AnovaPrecisionCookerSensor.TARGET_TEMPERATURE: 23.33,
        AnovaPrecisionCookerSensor.COOK_TIME_REMAINING: 0,
        AnovaPrecisionCookerSensor.FIRMWARE_VERSION: "2.2.0",
        AnovaPrecisionCookerSensor.HEATER_TEMPERATURE: 20.87,
        AnovaPrecisionCookerSensor.TRIAC_TEMPERATURE: 21.79,
        AnovaPrecisionCookerSensor.WATER_TEMPERATURE: 21.33,
    },
    "binary_sensors": {
        AnovaPrecisionCookerBinarySensor.COOKING: False,
        AnovaPrecisionCookerBinarySensor.DEVICE_SAFE: True,
        AnovaPrecisionCookerBinarySensor.WATER_LEAK: False,
        AnovaPrecisionCookerBinarySensor.WATER_LEVEL_CRITICAL: True,
        AnovaPrecisionCookerBinarySensor.WATER_TEMP_TOO_HIGH: False,
    },
}


def create_entry(hass: HomeAssistant) -> ConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data={"device_id": DEVICE_ID})
    entry.add_to_hass(hass)
    return entry


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
    error: str | None = None,
) -> ConfigEntry:
    """Set up the Slack integration in Home Assistant."""
    entry = create_entry(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
