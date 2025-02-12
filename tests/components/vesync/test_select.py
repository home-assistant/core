"""Tests for the select platform."""

from unittest.mock import patch

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.vesync.const import NIGHT_LIGHT_LEVEL_DIM
from homeassistant.components.vesync.select import HA_TO_VS_NIGHT_LIGHT_LEVEL_MAP
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT


async def test_set_nightlight_level(
    hass: HomeAssistant, config_entry: ConfigEntry, humidifier_300s, manager
) -> None:
    """Test set of night light level."""

    with (
        patch(
            "homeassistant.components.vesync.async_generate_device_list",
            return_value=[humidifier_300s],
        ),
        patch(
            "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_request_refresh"
        ) as coordinator_refresh,
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

        # Assert that setter API was invoked with the expected translated value
        method_mock.assert_called_once_with(
            HA_TO_VS_NIGHT_LIGHT_LEVEL_MAP[NIGHT_LIGHT_LEVEL_DIM]
        )
        # Assert that coordinator refresh was invoked
        assert coordinator_refresh.assert_called


async def test_nightlight_level(
    hass: HomeAssistant, config_entry: ConfigEntry, humidifier_300s, manager
) -> None:
    """Test the state of night light level select entity."""

    # The mocked device has night_light_brightness=50 which is "dim"
    with (
        patch(
            "homeassistant.components.vesync.async_generate_device_list",
            return_value=[humidifier_300s],
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert (
            hass.states.get(ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT).state
            == NIGHT_LIGHT_LEVEL_DIM
        )
