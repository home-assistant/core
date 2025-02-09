"""Tests for the select platform."""

from unittest.mock import patch

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.vesync.const import NIGHT_LIGHT_LEVEL_DIM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT


async def test_set_nightlight_level(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    humidifier_300s,
    manager,
) -> None:
    """Test update of display for sleep mode."""

    with patch(
        "homeassistant.components.vesync.async_generate_device_list",
        return_value=[humidifier_300s],
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with patch.object(humidifier_300s, "set_night_light_brightness") as method_mock:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT,
                ATTR_OPTION: NIGHT_LIGHT_LEVEL_DIM,
            },
            blocking=True,
        )
        method_mock.assert_called_once()
