"""Tests for the vaillant sensor."""

from pymultimatic.model import System
import pytest

import homeassistant.components.vaillant as vaillant

from tests.components.vaillant import (
    SystemManagerMock,
    assert_entities_count,
    goto_future,
    setup_vaillant,
)


@pytest.fixture(autouse=True)
def fixture_only_sensor(mock_system_manager):
    """Mock vaillant to only handle sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = ["sensor"]
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await setup_vaillant(hass)
    print(hass.states.async_entity_ids())
    assert_entities_count(hass, 2)


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await setup_vaillant(hass, system=System())
    assert_entities_count(hass, 0)


async def test_state_update(hass):
    """Test all sensors are updated accordingly to data."""
    assert await setup_vaillant(hass)
    assert_entities_count(hass, 2)

    assert hass.states.is_state("sensor.vaillant_waterpressuresensor", "1.9")
    assert hass.states.is_state("sensor.vaillant_outdoor_temperature", "18")

    system = SystemManagerMock.system
    system.outdoor_temperature = 21
    system.reports[0].value = 1.6
    SystemManagerMock.system = system

    await goto_future(hass)

    assert hass.states.is_state("sensor.vaillant_waterpressuresensor", "1.6")
    assert hass.states.is_state("sensor.vaillant_outdoor_temperature", "21")
