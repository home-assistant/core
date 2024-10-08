"""Test the Flipr sensor."""

from unittest.mock import AsyncMock

from flipr_api.exceptions import FliprError

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test the creation and values of the Flipr binary sensors."""

    await setup_integration(hass, mock_config_entry)

    # Check entity unique_id value that is generated in FliprEntity base class.
    entity = entity_registry.async_get("sensor.flipr_myfliprid_red_ox")
    assert entity.unique_id == "myfliprid-red_ox"

    state = hass.states.get("sensor.flipr_myfliprid_ph")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "7.03"

    state = hass.states.get("sensor.flipr_myfliprid_water_temperature")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "10.5"

    state = hass.states.get("sensor.flipr_myfliprid_last_measured")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.state == "2021-02-15T09:10:32+00:00"

    state = hass.states.get("sensor.flipr_myfliprid_red_ox")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "mV"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "657.58"

    state = hass.states.get("sensor.flipr_myfliprid_chlorine")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "mV"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "0.23654886"

    state = hass.states.get("sensor.flipr_myfliprid_battery")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "95.0"


async def test_error_flipr_api_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test the Flipr sensors error."""

    mock_flipr_client.get_pool_measure_latest.side_effect = FliprError(
        "Error during flipr data retrieval..."
    )

    await setup_integration(hass, mock_config_entry)

    # Check entity is not generated because of the FliprError raised.
    entity = entity_registry.async_get("sensor.flipr_myfliprid_red_ox")
    assert entity is None
