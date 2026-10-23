"""Tests for rainforest eagle sensors."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.rainforest_eagle.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import MOCK_200_RESPONSE_WITH_PRICE, MOCK_200_RESPONSE_WITHOUT_PRICE

from tests.common import async_fire_time_changed


async def test_sensors_200(hass: HomeAssistant, setup_rainforest_200) -> None:
    """Test the sensors."""
    assert len(hass.states.async_all()) == 3

    demand = hass.states.get("sensor.eagle_200_power_demand")
    assert demand is not None
    assert demand.state == "1.152000"
    assert demand.attributes["unit_of_measurement"] == "kW"

    delivered = hass.states.get("sensor.eagle_200_total_energy_delivered")
    assert delivered is not None
    assert delivered.state == "45251.285000"
    assert delivered.attributes["unit_of_measurement"] == "kWh"

    received = hass.states.get("sensor.eagle_200_total_energy_received")
    assert received is not None
    assert received.state == "232.232000"
    assert received.attributes["unit_of_measurement"] == "kWh"

    setup_rainforest_200.get_device_query.return_value = MOCK_200_RESPONSE_WITH_PRICE

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 4

    price = hass.states.get("sensor.eagle_200_energy_price")
    assert price is not None
    assert price.state == "0.053990"
    assert price.attributes["unit_of_measurement"] == "USD/kWh"


async def test_sensors_100(hass: HomeAssistant, setup_rainforest_100) -> None:
    """Test the sensors."""
    assert len(hass.states.async_all()) == 3

    demand = hass.states.get("sensor.eagle_100_power_demand")
    assert demand is not None
    assert demand.state == "1.152000"
    assert demand.attributes["unit_of_measurement"] == "kW"

    delivered = hass.states.get("sensor.eagle_100_total_energy_delivered")
    assert delivered is not None
    assert delivered.state == "45251.285000"
    assert delivered.attributes["unit_of_measurement"] == "kWh"

    received = hass.states.get("sensor.eagle_100_total_energy_received")
    assert received is not None
    assert received.state == "232.232000"
    assert received.attributes["unit_of_measurement"] == "kWh"


async def _refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance to the next coordinator poll."""
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("variable", "entity_id", "valid_state"),
    [
        pytest.param(
            "zigbee:CurrentSummationDelivered",
            "sensor.eagle_200_total_energy_delivered",
            "45251.285000",
            id="delivered",
        ),
        pytest.param(
            "zigbee:CurrentSummationReceived",
            "sensor.eagle_200_total_energy_received",
            "232.232000",
            id="received",
        ),
    ],
)
async def test_invalid_summation_200(
    hass: HomeAssistant,
    setup_rainforest_200: Mock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    variable: str,
    entity_id: str,
    valid_state: str,
) -> None:
    """Test a summation at the top of the 48-bit range is ignored."""
    invalid_response = deepcopy(MOCK_200_RESPONSE_WITHOUT_PRICE)
    # 0xfffffffffff0 Wh, as reported by a meter in place of a real reading.
    invalid_response[variable]["Value"] = "281474976710.640"
    setup_rainforest_200.get_device_query.return_value = invalid_response

    await _refresh(hass, freezer)

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert f"Ignoring invalid {variable} from meter" in caplog.text

    setup_rainforest_200.get_device_query.return_value = MOCK_200_RESPONSE_WITHOUT_PRICE

    await _refresh(hass, freezer)

    assert hass.states.get(entity_id).state == valid_state


async def test_non_numeric_summation_200(
    hass: HomeAssistant,
    setup_rainforest_200: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a non-numeric summation does not make the other sensors unavailable."""
    response = deepcopy(MOCK_200_RESPONSE_WITHOUT_PRICE)
    response["zigbee:CurrentSummationDelivered"]["Value"] = "invalid"
    setup_rainforest_200.get_device_query.return_value = response
    await _refresh(hass, freezer)

    assert hass.states.get("sensor.eagle_200_power_demand").state == "1.152000"
    assert hass.states.get("sensor.eagle_200_total_energy_received").state == (
        "232.232000"
    )
