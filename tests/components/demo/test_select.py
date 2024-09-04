"""The tests for the demo select component."""

from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

ENTITY_SPEED = "select.speed"


@pytest.fixture
async def select_only() -> None:
    """Enable only the select platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.SELECT],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_select(hass: HomeAssistant, select_only) -> None:
    """Initialize setup demo select entity."""
    assert await async_setup_component(hass, DOMAIN, {"select": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_SPEED)
    assert state
    assert state.state == "ridiculous_speed"
    assert state.attributes.get(ATTR_OPTIONS) == [
        "light_speed",
        "ridiculous_speed",
        "ludicrous_speed",
    ]


async def test_select_option_bad_attr(hass: HomeAssistant) -> None:
    """Test selecting a different option with invalid option value."""
    state = hass.states.get(ENTITY_SPEED)
    assert state
    assert state.state == "ridiculous_speed"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "slow_speed", ATTR_ENTITY_ID: ENTITY_SPEED},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SPEED)
    assert state
    assert state.state == "ridiculous_speed"


async def test_select_option(hass: HomeAssistant) -> None:
    """Test selecting of a option."""
    state = hass.states.get(ENTITY_SPEED)
    assert state
    assert state.state == "ridiculous_speed"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "light_speed", ATTR_ENTITY_ID: ENTITY_SPEED},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SPEED)
    assert state
    assert state.state == "light_speed"
