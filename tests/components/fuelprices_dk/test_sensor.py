"""Test sensor platform for Fuelprices.dk."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_PRICES

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities."""
    with patch("homeassistant.components.fuelprices_dk.PLATFORMS", ["sensor"]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_updates(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor updates when the coordinator refreshes."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "14.29"

    mock_braendstofpriser.get_prices.return_value = {
        "station": {"id": 1234, "name": "Aarhus C", "last_update": None},
        "prices": {**TEST_PRICES, "Blyfri95": 15.99},
    }

    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "15.99"


async def test_sensor_becomes_unavailable_when_product_missing(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor becomes unavailable when its product is not returned."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "14.29"

    remaining = {k: v for k, v in TEST_PRICES.items() if k != "Blyfri95"}
    mock_braendstofpriser.get_prices.return_value = {
        "station": {"id": 1234, "name": "Aarhus C", "last_update": None},
        "prices": remaining,
    }

    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == STATE_UNAVAILABLE


async def test_sensor_ignores_non_numeric_price(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor reports unknown when the API returns a non-numeric price."""
    await setup_integration(hass, mock_config_entry)

    mock_braendstofpriser.get_prices.return_value = {
        "station": {"id": 1234, "name": "Aarhus C", "last_update": None},
        "prices": {**TEST_PRICES, "Blyfri95": "n/a"},
    }

    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == STATE_UNKNOWN
