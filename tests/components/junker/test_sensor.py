"""Tests for the Junker sensors."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.junker.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

PREFIX = "test municipality:all"


def _state(hass: HomeAssistant, unique_id: str):
    """Return the state of the sensor with the given unique ID."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{PREFIX}_{unique_id}"
    )
    return hass.states.get(entity_id) if entity_id else None


@pytest.mark.freeze_time("2026-11-10 20:00:00")
@pytest.mark.usefixtures("init_integration")
async def test_sensors(hass: HomeAssistant) -> None:
    """Test the days and tomorrow sensors."""
    assert _state(hass, "organic waste").state == "1"
    assert _state(hass, "paper").state == "1"
    assert _state(hass, "general waste") is None

    tomorrow = _state(hass, "tomorrow_collection")
    assert tomorrow.state == "Kitchen, Cardboard"
    assert tomorrow.attributes["waste_types"] == ["Kitchen", "Cardboard"]


@pytest.mark.freeze_time("2026-11-11 20:00:00")
@pytest.mark.usefixtures("init_integration")
async def test_today_excluded(hass: HomeAssistant) -> None:
    """Test today's collection is ignored and tomorrow's sensor is unavailable."""
    assert _state(hass, "organic waste").state == STATE_UNKNOWN
    assert _state(hass, "tomorrow_collection").state == STATE_UNAVAILABLE


@pytest.mark.freeze_time("2026-11-10 20:00:00")
@pytest.mark.usefixtures("init_integration")
async def test_midnight_refresh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the states are refreshed after midnight."""
    assert _state(hass, "tomorrow_collection").state != STATE_UNAVAILABLE

    freezer.move_to("2026-11-11 08:00:10")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert _state(hass, "tomorrow_collection").state == STATE_UNAVAILABLE
