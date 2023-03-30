"""Tests for the sensors provided by the EnergyZero integration."""

from unittest.mock import MagicMock

from energyzero import EnergyZeroNoDataError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.energyzero.const import DOMAIN
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

pytestmark = [pytest.mark.freeze_time("2022-12-07 23:15:00")]


@pytest.mark.usefixtures("init_integration")
async def test_last_hour_price(hass: HomeAssistant, mock_energyzero: MagicMock) -> None:
    """Test the EnergyZero - Validate the next hour price on the last hour of the day."""
    await async_setup_component(hass, "homeassistant", {})

    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.energyzero_today_energy_next_hour_price"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.energyzero_today_energy_next_hour_price"))
    assert state.state == "0.32"
