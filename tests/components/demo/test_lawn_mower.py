"""The tests for the Demo lawn mower platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    SERVICE_STOP,
    LawnMowerActivity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_PLATFORM,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

ENTITY_LAWN_MOWER = "lawn_mower.my_lawn_mower"


@pytest.fixture
async def lawn_mower_only() -> AsyncGenerator[None]:
    """Enable only the lawn mower platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.LAWN_MOWER],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_lawn_mower(hass: HomeAssistant, lawn_mower_only: None):
    """Initialize setup demo lawn mower."""
    assert await async_setup_component(
        hass, LAWN_MOWER_DOMAIN, {LAWN_MOWER_DOMAIN: {CONF_PLATFORM: "demo"}}
    )
    await hass.async_block_till_done()


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test lawn mower supported features."""
    state = hass.states.get("lawn_mower.my_lawn_mower")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 15
    assert state.state == LawnMowerActivity.DOCKED


async def test_methods(hass: HomeAssistant) -> None:
    """Test if methods call the services as expected."""
    await hass.services.async_call(
        LAWN_MOWER_DOMAIN,
        SERVICE_START_MOWING,
        {ATTR_ENTITY_ID: ENTITY_LAWN_MOWER},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LAWN_MOWER)
    assert state.state == LawnMowerActivity.MOWING

    await hass.services.async_call(
        LAWN_MOWER_DOMAIN,
        SERVICE_STOP,
        {ATTR_ENTITY_ID: ENTITY_LAWN_MOWER},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LAWN_MOWER)
    assert state.state == LawnMowerActivity.IDLE

    await hass.services.async_call(
        LAWN_MOWER_DOMAIN,
        SERVICE_PAUSE,
        {ATTR_ENTITY_ID: ENTITY_LAWN_MOWER},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LAWN_MOWER)
    assert state.state == LawnMowerActivity.PAUSED

    await hass.services.async_call(
        LAWN_MOWER_DOMAIN,
        SERVICE_DOCK,
        {ATTR_ENTITY_ID: ENTITY_LAWN_MOWER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_LAWN_MOWER)
    assert state.state == LawnMowerActivity.RETURNING

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LAWN_MOWER)
    assert state.state == LawnMowerActivity.DOCKED
