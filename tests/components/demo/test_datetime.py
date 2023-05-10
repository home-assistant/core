"""The tests for the demo datetime component."""
import pytest

from homeassistant.components.datetime import ATTR_DATETIME, DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_DATETIME = "datetime.date_and_time"


@pytest.fixture(autouse=True)
async def setup_demo_datetime(hass: HomeAssistant) -> None:
    """Initialize setup demo datetime."""
    assert await async_setup_component(hass, DOMAIN, {"datetime": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_DATETIME)
    assert state.state == "2020-01-01T12:00:00+00:00"


async def test_set_datetime(hass: HomeAssistant) -> None:
    """Test set datetime service."""
    hass.config.set_time_zone("UTC")
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_DATETIME, ATTR_DATETIME: "2021-02-03 01:02:03"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_DATETIME)
    assert state.state == "2021-02-03T01:02:03+00:00"
