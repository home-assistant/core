"""The test for the moon sensor platform."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.moon.sensor import (
    MOON_ICONS,
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    "moon_value,native_value,icon",
    [
        (0, STATE_NEW_MOON, MOON_ICONS[STATE_NEW_MOON]),
        (5, STATE_WAXING_CRESCENT, MOON_ICONS[STATE_WAXING_CRESCENT]),
        (7, STATE_FIRST_QUARTER, MOON_ICONS[STATE_FIRST_QUARTER]),
        (12, STATE_WAXING_GIBBOUS, MOON_ICONS[STATE_WAXING_GIBBOUS]),
        (14.3, STATE_FULL_MOON, MOON_ICONS[STATE_FULL_MOON]),
        (20.1, STATE_WANING_GIBBOUS, MOON_ICONS[STATE_WANING_GIBBOUS]),
        (20.8, STATE_LAST_QUARTER, MOON_ICONS[STATE_LAST_QUARTER]),
        (23, STATE_WANING_CRESCENT, MOON_ICONS[STATE_WANING_CRESCENT]),
    ],
)
async def test_moon_day(
    hass: HomeAssistant, moon_value: float, native_value: str, icon: str
) -> None:
    """Test the Moon sensor."""
    config = {"sensor": {"platform": "moon"}}

    await async_setup_component(hass, HA_DOMAIN, {})
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.moon")

    with patch(
        "homeassistant.components.moon.sensor.moon.phase", return_value=moon_value
    ):
        await async_update_entity(hass, "sensor.moon")

    state = hass.states.get("sensor.moon")
    assert state.state == native_value
    assert state.attributes["icon"] == icon


async def async_update_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Run an update action for an entity."""
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
