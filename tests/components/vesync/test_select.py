"""Tests for the select platform."""

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.vesync.const import HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM
from homeassistant.components.vesync.select import (
    HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT


@pytest.mark.parametrize(
    "install_humidifier_device", ["humidifier_300s"], indirect=True
)
async def test_humidifier_set_nightlight_level(
    hass: HomeAssistant, manager, humidifier_300s, install_humidifier_device
) -> None:
    """Test set of humidifier night light level."""

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT,
            ATTR_OPTION: HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
        },
        blocking=True,
    )

    # Assert that setter API was invoked with the expected translated value
    humidifier_300s.set_night_light_brightness.assert_called_once_with(
        HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP[HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM]
    )
    # Assert that devices were refreshed
    manager.update_all_devices.assert_called_once()


@pytest.mark.parametrize(
    "install_humidifier_device", ["humidifier_300s"], indirect=True
)
async def test_humidifier_nightlight_level(
    hass: HomeAssistant, install_humidifier_device
) -> None:
    """Test the state of humidifier night light level select entity."""

    # The mocked device has night_light_brightness=50 which is "dim"
    assert (
        hass.states.get(ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT).state
        == HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM
    )
