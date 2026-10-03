"""Tests Discovergy sensor component."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pydiscovergy.error import DiscovergyClientError, HTTPError, InvalidLogin
from pydiscovergy.models import Reading
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.discovergy.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .const import LAST_READING, LAST_READING_GAS

from tests.common import MockConfigEntry, async_fire_time_changed

CONSUMPTION = "sensor.electricity_teststrasse_1_total_consumption"
PRODUCTION = "sensor.electricity_teststrasse_1_total_production"
POWER = "sensor.electricity_teststrasse_1_total_power"

# The API occasionally delivers a reading whose total-increasing registers are 0.
ZERO_TOTALS_READING = Reading(
    time=LAST_READING.time,
    values={**LAST_READING.values, "energy": 0.0, "energyOut": 0.0},
)


def _electricity_reading(reading: Reading):
    """Return a meter_last_reading side effect serving the given electricity reading."""
    return lambda meter_id: (
        LAST_READING_GAS if meter_id == "d81a652fe0824f9a9d336016587d3b9d" else reading
    )


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


@pytest.mark.usefixtures("setup_integration")
async def test_sensor_zero_total_reading(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    discovergy: AsyncMock,
) -> None:
    """Test a zero reading of a register that has counted is not passed on.

    Reporting it would make the recorder book a meter reset and count the
    whole register as new consumption once the real value returns.
    """
    state = hass.states.get(CONSUMPTION)
    assert state
    assert state.state == "11934.8699715"

    discovergy.meter_last_reading.side_effect = _electricity_reading(
        ZERO_TOTALS_READING
    )
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(CONSUMPTION)
    assert state
    assert state.state == "unavailable"
    state = hass.states.get(PRODUCTION)
    assert state
    assert state.state == "unavailable"
    # measurement sensors legitimately read 0 and are not affected
    state = hass.states.get(POWER)
    assert state
    assert state.state == "0.0"

    discovergy.meter_last_reading.side_effect = _electricity_reading(LAST_READING)
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(CONSUMPTION)
    assert state
    assert state.state == "11934.8699715"


async def test_sensor_zero_total_never_counted(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    discovergy: AsyncMock,
) -> None:
    """Test a register that has never counted (e.g. no production) reads 0."""
    discovergy.meter_last_reading.side_effect = _electricity_reading(
        ZERO_TOTALS_READING
    )
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    state = hass.states.get(PRODUCTION)
    assert state
    assert state.state == "0.0"
