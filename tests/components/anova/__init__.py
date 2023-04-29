"""Tests for the Anova integration."""
from __future__ import annotations

from unittest.mock import patch

from anova_wifi import (
    AnovaPrecisionCooker,
    AnovaPrecisionCookerBinarySensor,
    AnovaPrecisionCookerSensor,
)

from homeassistant.components.anova.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_UNIQUE_ID = "abc123def"

CONF_INPUT = {CONF_USERNAME: "sample@gmail.com", CONF_PASSWORD: "sample"}

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


def create_entry(hass: HomeAssistant, device_id: str = DEVICE_UNIQUE_ID) -> ConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Anova",
        data={
            CONF_USERNAME: "sample@gmail.com",
            CONF_PASSWORD: "sample",
            "devices": [(device_id, "type_sample")],
        },
        unique_id="sample@gmail.com",
    )
    entry.add_to_hass(hass)
    return entry


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
    error: str | None = None,
) -> ConfigEntry:
    """Set up the Anova integration in Home Assistant."""
    with patch(
        "homeassistant.components.anova.coordinator.AnovaPrecisionCooker.update"
    ) as update_patch, patch(
        "homeassistant.components.anova.AnovaApi.authenticate"
    ), patch(
        "homeassistant.components.anova.AnovaApi.get_devices"
    ) as device_patch:
        update_patch.return_value = ONLINE_UPDATE
        device_patch.return_value = [
            AnovaPrecisionCooker(None, DEVICE_UNIQUE_ID, "type_sample", None)
        ]

        entry = create_entry(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        return entry
