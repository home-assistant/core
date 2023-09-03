"""The tests for the demo date component."""
from unittest.mock import patch

import pytest

from homeassistant.components.date import ATTR_DATE, DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_DATE = "date.date"


@pytest.fixture
async def date_only() -> None:
    """Enable only the date platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.DATE],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_date(hass: HomeAssistant, date_only) -> None:
    """Initialize setup demo date."""
    assert await async_setup_component(hass, DOMAIN, {"date": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_DATE)
    assert state.state == "2020-01-01"


async def test_set_datetime(hass: HomeAssistant) -> None:
    """Test set datetime service."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_DATE, ATTR_DATE: "2021-02-03"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_DATE)
    assert state.state == "2021-02-03"
