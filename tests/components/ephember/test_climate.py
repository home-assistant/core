"""Tests for the EPH Controls Ember climate platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyephember2.pyephember2 import ZoneMode
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CONFIG = {
    CLIMATE_DOMAIN: {
        "platform": "ephember",
        "username": "user@example.com",
        "password": "password",
    }
}


def _zone(zoneid, name, device_type, points):
    return {
        "zoneid": zoneid,
        "name": name,
        "deviceType": device_type,
        "pointDataList": [
            {"pointIndex": index, "value": str(value)}
            for index, value in points.items()
        ],
    }


# Point 5 current temp, 6 target temp, 7 mode, 10 boiler state
RADIATORS = _zone("zone1", "Radiators", 2, {5: 200, 6: 205, 7: 2, 10: 2})
HOT_WATER = _zone("zone2", "Hot Water", 4, {5: 250, 6: 600, 7: 3, 10: 1})


@pytest.fixture
def mock_ember() -> Generator[MagicMock]:
    """Mock the EphEmber client."""
    with patch(
        "homeassistant.components.ephember.climate.EphEmber", autospec=True
    ) as mock_class:
        ember = mock_class.return_value
        homes = [{"zones": [RADIATORS, HOT_WATER]}]
        ember.get_zones.return_value = homes
        ember.get_zone.side_effect = lambda zoneid: next(
            zone for zone in homes[0]["zones"] if zone["zoneid"] == zoneid
        )
        yield ember


async def test_climate_entities(hass: HomeAssistant, mock_ember: MagicMock) -> None:
    """Test zones are set up as climate entities."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("climate.radiators")
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 20.0
    assert state.attributes[ATTR_TEMPERATURE] == 20.5
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING

    state = hass.states.get("climate.hot_water")
    assert state.state == HVACMode.OFF
    assert state.attributes["current_temperature"] == 25.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_set_temperature_and_mode(
    hass: HomeAssistant, mock_ember: MagicMock
) -> None:
    """Test changing target temperature and mode."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.radiators", ATTR_TEMPERATURE: 21.5},
        blocking=True,
    )
    mock_ember.set_zone_target_temperature.assert_called_once_with("zone1", 21.5)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.radiators", ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_ember.set_zone_mode.assert_called_once_with("zone1", ZoneMode.OFF)


async def test_unavailable_when_cloud_unreachable(
    hass: HomeAssistant,
    mock_ember: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entities become unavailable, log once, and recover."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    mock_ember.get_zones.side_effect = RuntimeError("Host is unreachable")
    for _ in range(3):
        freezer.tick(timedelta(minutes=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("climate.radiators").state == STATE_UNAVAILABLE
    assert caplog.text.count("Unable to update Radiators") == 1

    mock_ember.get_zones.side_effect = None
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("climate.radiators").state == HVACMode.HEAT
    assert "Radiators is available again" in caplog.text


async def test_setup_retries_when_login_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test platform setup is retried when the cloud cannot be reached."""
    with patch(
        "homeassistant.components.ephember.climate.EphEmber",
        side_effect=RuntimeError("Unable to login."),
    ):
        assert await async_setup_component(hass, CLIMATE_DOMAIN, CONFIG)
        await hass.async_block_till_done()

    assert hass.states.async_entity_ids(CLIMATE_DOMAIN) == []
    assert "Platform ephember not ready yet" in caplog.text
