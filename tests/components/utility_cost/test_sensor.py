"""The tests for the utility_cost sensor platform."""
from typing import NamedTuple, Optional

import pytest

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_KILO_WATT_HOUR,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import mock_restore_cache


async def test_state(hass) -> None:
    """Test utility cost sensor state."""

    utility_entity_id = "sensor.utility"
    price_entity_id = "sensor.price"
    config = {
        "sensor": {
            "platform": "utility_cost",
            "name": "utility_cost",
            "utility_source": utility_entity_id,
            "price_source": price_entity_id,
        }
    }
    utility_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
    }
    price_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: "EUR/kWh",
    }

    assert await async_setup_component(hass, "sensor", config)

    hass.states.async_set(utility_entity_id, 2, utility_attributes)
    hass.states.async_set(price_entity_id, 10, price_attributes)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state is not None
    assert state.attributes.get("unit_of_measurement") is None
    assert state.attributes.get("device_class") == SensorDeviceClass.MONETARY
    assert state.attributes.get("state_class") is SensorStateClass.TOTAL

    hass.states.async_set(utility_entity_id, 3, utility_attributes, force_update=True)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state is not None

    # Testing 1 kWh energy consumption (from 2 to 3 kWh) at 10 EUR/kWh which should give 10 EUR
    assert round(float(state.state), 2) == 10.0

    assert state.attributes.get("unit_of_measurement") == "EUR"
    assert state.attributes.get("device_class") == SensorDeviceClass.MONETARY
    assert state.attributes.get("state_class") is SensorStateClass.TOTAL


async def test_restore_state(hass: HomeAssistant) -> None:
    """Test utility cost sensor state is restored correctly."""
    mock_restore_cache(
        hass,
        (
            State(
                "sensor.utility_cost",
                "100.0",
                {
                    "last_period": "2.0",
                    "unit_of_measurement": "EUR",
                },
            ),
        ),
    )

    config = {
        "sensor": {
            "platform": "utility_cost",
            "name": "utility_cost",
            "utility_source": "sensor.utility",
            "price_source": "sensor.price",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state
    assert state.state == "100.0"
    assert state.attributes.get("unit_of_measurement") == "EUR"
    assert state.attributes.get("last_period") == "2.0"


async def test_restore_state_failed(hass: HomeAssistant) -> None:
    """Test utility cost sensor state is restored correctly."""
    mock_restore_cache(
        hass,
        (
            State(
                "sensor.utility_cost",
                "INVALID",
                {
                    "last_reset": "2019-10-06T21:00:00.000000",
                },
            ),
        ),
    )

    config = {
        "sensor": {
            "platform": "utility_cost",
            "name": "utility_cost",
            "utility_source": "sensor.utility",
            "price_source": "sensor.price",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("unit_of_measurement") is None
    assert state.attributes.get("state_class") is SensorStateClass.TOTAL
    assert state.attributes.get("device_class") == SensorDeviceClass.MONETARY
    assert state.attributes.get("last_period") == "0"


async def test_update_monotonic(hass):
    """Test Utility cost sensor state."""

    utility_entity_id = "sensor.utility"
    price_entity_id = "sensor.price"
    config = {
        "sensor": {
            "platform": "utility_cost",
            "name": "utility_cost",
            "utility_source": utility_entity_id,
            "price_source": price_entity_id,
        }
    }
    utility_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
    }
    price_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: "EUR/kWh",
    }

    assert await async_setup_component(hass, "sensor", config)

    hass.states.async_set(price_entity_id, 0, price_attributes)
    hass.states.async_set(utility_entity_id, 1, utility_attributes)
    await hass.async_block_till_done()

    # Testing a monotonically increasing energy sensor with varying price
    for energy, price in (2, 1), (5, 20), (22, 6):
        hass.states.async_set(price_entity_id, price, price_attributes)
        hass.states.async_set(utility_entity_id, energy, utility_attributes)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state is not None

    assert float(state.state) == (2 - 1) * 1 + (5 - 2) * 20 + (22 - 5) * 6


async def test_update_with_reset(hass):
    """Test Utility cost sensor state."""

    utility_entity_id = "sensor.utility"
    price_entity_id = "sensor.price"
    config = {
        "sensor": {
            "platform": "utility_cost",
            "name": "utility_cost",
            "utility_source": utility_entity_id,
            "price_source": price_entity_id,
        }
    }
    utility_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }
    price_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: "EUR/kWh",
    }

    assert await async_setup_component(hass, "sensor", config)

    hass.states.async_set(price_entity_id, 0, price_attributes)
    hass.states.async_set(utility_entity_id, 1, utility_attributes)
    await hass.async_block_till_done()

    # Testing an energy sensor with varying price and a reset in the middle
    for energy, price in (5, 2), (0, 20), (10, 5):
        hass.states.async_set(price_entity_id, price, price_attributes)
        hass.states.async_set(utility_entity_id, energy, utility_attributes)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state is not None

    assert float(state.state) == 10 * 5
    assert float(state.attributes.get("last_period")) == (5 - 1) * 2


async def test_update_with_last_reset(hass):
    """Test Utility Cost sensor state."""

    utility_entity_id = "sensor.utility"
    price_entity_id = "sensor.price"
    config = {
        "sensor": {
            "platform": "utility_cost",
            "name": "utility_cost",
            "utility_source": utility_entity_id,
            "price_source": price_entity_id,
        }
    }
    old_reset = dt_util.utc_from_timestamp(0).isoformat()
    new_reset = dt_util.utcnow().isoformat()
    utility_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        ATTR_LAST_RESET: old_reset,
    }
    price_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: "EUR/kWh",
    }

    assert await async_setup_component(hass, "sensor", config)

    hass.states.async_set(price_entity_id, 0, price_attributes)
    hass.states.async_set(utility_entity_id, 1, utility_attributes)
    await hass.async_block_till_done()

    # Testing an energy sensor with varying price and a reset in the middle
    for energy, price, reset in (5, 2, False), (2, 20, True), (10, 5, False):
        if reset:
            utility_attributes[ATTR_LAST_RESET] = new_reset
        hass.states.async_set(price_entity_id, price, price_attributes)
        hass.states.async_set(utility_entity_id, energy, utility_attributes)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state is not None

    assert float(state.state) == (10 - 2) * 5
    assert float(state.attributes.get("last_period")) == (5 - 1) * 2


async def test_utility_initialization(hass):
    """Test Utility Cost sensor initialization using an energy source."""
    utility_entity_id = "sensor.utility"
    price_entity_id = "sensor.price"
    config = {
        "sensor": {
            "platform": "utility_cost",
            "name": "utility_cost",
            "utility_source": utility_entity_id,
            "price_source": price_entity_id,
        }
    }
    utility_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
    }
    price_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: "EUR/kWh",
    }

    assert await async_setup_component(hass, "sensor", config)

    hass.states.async_set(price_entity_id, 2, price_attributes)
    await hass.async_block_till_done()

    # This replicates the current sequence when HA starts up in a real runtime
    # by updating the base sensor state before the base sensor's units
    # or state have been correctly populated.  Those interim updates
    # include states of None and Unknown
    hass.states.async_set(utility_entity_id, 100, utility_attributes)
    await hass.async_block_till_done()
    hass.states.async_set(utility_entity_id, 200, utility_attributes)
    await hass.async_block_till_done()

    utility_attributes[ATTR_UNIT_OF_MEASUREMENT] = ENERGY_KILO_WATT_HOUR
    hass.states.async_set(utility_entity_id, 300, utility_attributes)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state is not None

    # Testing the sensor ignored the source sensor's units until
    # they became valid
    assert state.attributes.get("unit_of_measurement") == "EUR"

    # When source state goes to None / Unknown, expect an early exit without
    # changes to the state or unit_of_measurement
    hass.states.async_set(utility_entity_id, STATE_UNAVAILABLE, None)
    await hass.async_block_till_done()

    new_state = hass.states.get("sensor.utility_cost")
    assert state == new_state
    assert state.attributes.get("unit_of_measurement") == "EUR"


async def test_price_initialization(hass):
    """Test Utility Cost sensor initialization using an energy source."""
    utility_entity_id = "sensor.utility"
    price_entity_id = "sensor.price"
    config = {
        "sensor": {
            "platform": "utility_cost",
            "name": "utility_cost",
            "utility_source": utility_entity_id,
            "price_source": price_entity_id,
        }
    }
    utility_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
    }
    price_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: None,
    }

    assert await async_setup_component(hass, "sensor", config)

    # This tests the sensor initialization when the price is not yet
    # ready due to a missing unit
    hass.states.async_set(price_entity_id, 2, price_attributes)
    await hass.async_block_till_done()

    # Any readings from the energy sensor should be ignored
    hass.states.async_set(utility_entity_id, 100, utility_attributes)
    await hass.async_block_till_done()
    hass.states.async_set(utility_entity_id, 200, utility_attributes)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("unit_of_measurement") is None

    # Now make the price available and submit another energy reading
    price_attributes[ATTR_UNIT_OF_MEASUREMENT] = "EUR/kWh"
    hass.states.async_set(price_entity_id, 3, price_attributes)
    await hass.async_block_till_done()

    hass.states.async_set(utility_entity_id, 300, utility_attributes)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.utility_cost")
    assert state is not None
    assert float(state.state) == (300 - 200) * 3
    assert state.attributes.get("unit_of_measurement") == "EUR"

    # When price state goes to None / Unknown, expect an early exit without
    # changes to the state or unit_of_measurement
    hass.states.async_set(price_entity_id, STATE_UNAVAILABLE, None)
    await hass.async_block_till_done()
    hass.states.async_set(utility_entity_id, 400, utility_attributes)
    await hass.async_block_till_done()

    new_state = hass.states.get("sensor.utility_cost")
    assert state == new_state
    assert state.attributes.get("unit_of_measurement") == "EUR"


class CurrencyUnitTest(NamedTuple):
    """Data for resulting currency unit tests."""

    price_unit: Optional[str]
    utility_unit: Optional[str]
    expected_currency: Optional[str]


@pytest.mark.parametrize(
    "test",
    [
        # Valid units
        CurrencyUnitTest("EUR/kWh", "kWh", "EUR"),
        CurrencyUnitTest("EUR/Wh", "Wh", "EUR"),
        CurrencyUnitTest("NOK/kWh", "kWh", "NOK"),
        CurrencyUnitTest("USD/MB", "MB", "USD"),
        CurrencyUnitTest("X/Cat", "Cat", "X"),
        # Invalid units
        CurrencyUnitTest("/kWh", "kWh", None),
        CurrencyUnitTest("EUR/", "kWh", None),
        CurrencyUnitTest("EUR", "kWh", None),
        CurrencyUnitTest("", "kWh", None),
        CurrencyUnitTest("EUR", "", None),
        CurrencyUnitTest(None, "kWh", None),
        CurrencyUnitTest("EUR", None, None),
        # Prefix factor conversions: May want to add support for these later
        CurrencyUnitTest("EUR/kWh", "Wh", None),
        CurrencyUnitTest("EUR/Wh", "kWh", None),
    ],
)
async def test_currency_units(hass, test):
    """Test Utility Cost sensor's resulting currency based on the price and utility units."""
    utility_entity_id = "sensor.utility"
    price_entity_id = "sensor.price"
    config = {
        "sensor": {
            "platform": "utility_cost",
            "name": "utility_cost",
            "utility_source": utility_entity_id,
            "price_source": price_entity_id,
        }
    }
    utility_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: test.utility_unit,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
    }
    price_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: test.price_unit,
    }

    assert await async_setup_component(hass, "sensor", config)

    hass.states.async_set(price_entity_id, 2, price_attributes)
    await hass.async_block_till_done()

    # Only price set, our state should not have changed
    state = hass.states.get("sensor.utility_cost")
    assert state is not None
    assert state.attributes.get("unit_of_measurement") is None

    hass.states.async_set(utility_entity_id, 100, utility_attributes)
    await hass.async_block_till_done()

    # Both price and a utility reading is complete, our unit should be ready now
    state = hass.states.get("sensor.utility_cost")
    assert state is not None
    assert state.attributes.get("unit_of_measurement") == test.expected_currency
