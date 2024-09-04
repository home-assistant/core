"""Tests for the Tankerkoening integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.tankerkoenig import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import PRICES_MISSING_FUELTYPE, STATION_MISSING_FUELTYPE

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_integration")
async def test_sensor(
    hass: HomeAssistant,
    tankerkoenig: AsyncMock,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the tankerkoenig sensors."""

    state = hass.states.get("sensor.station_somewhere_street_1_super_e10")
    assert state
    assert state.state == "1.659"
    assert state.attributes == snapshot

    state = hass.states.get("sensor.station_somewhere_street_1_super")
    assert state
    assert state.state == "1.719"
    assert state.attributes == snapshot

    state = hass.states.get("sensor.station_somewhere_street_1_diesel")
    assert state
    assert state.state == "1.659"
    assert state.attributes == snapshot


async def test_sensor_missing_fueltype(
    hass: HomeAssistant,
    tankerkoenig: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the tankerkoenig sensors."""
    tankerkoenig.station_details.return_value = STATION_MISSING_FUELTYPE
    tankerkoenig.prices.return_value = PRICES_MISSING_FUELTYPE

    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.station_somewhere_street_1_super_e10")
    assert state

    state = hass.states.get("sensor.station_somewhere_street_1_super")
    assert state

    state = hass.states.get("sensor.station_somewhere_street_1_diesel")
    assert not state
