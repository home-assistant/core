"""Tests Discovergy sensor component."""
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pydiscovergy.error import DiscovergyClientError, HTTPError, InvalidLogin
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    "state_name",
    [
        "sensor.electricity_teststrasse_1_total_consumption",
        "sensor.electricity_teststrasse_1_total_power",
        "sensor.electricity_teststrasse_1_last_transmitted",
        "sensor.gas_teststrasse_1_total_gas_consumption",
        "sensor.gas_teststrasse_1_last_transmitted",
    ],
    ids=[
        "electricity total consumption",
        "electricity total power",
        "electricity last transmitted",
        "gas total consumption",
        "gas last transmitted",
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_name: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor setup and update."""

    entry = entity_registry.async_get(state_name)
    assert entry == snapshot

    state = hass.states.get(state_name)
    assert state == snapshot


@pytest.mark.parametrize(
    "error",
    [
        InvalidLogin,
        HTTPError,
        DiscovergyClientError,
        Exception,
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_sensor_update_fail(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    discovergy: AsyncMock,
    error: Exception,
) -> None:
    """Test sensor errors."""
    state = hass.states.get("sensor.electricity_teststrasse_1_total_consumption")
    assert state
    assert state.state == "11934.8699715"

    discovergy.meter_last_reading.side_effect = error

    freezer.tick(timedelta(minutes=1))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.electricity_teststrasse_1_total_consumption")
    assert state
    assert state.state == "unavailable"
