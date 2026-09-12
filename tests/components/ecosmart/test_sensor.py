"""Test the ecosmart sensors."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aioecosmart import EcosmartConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecosmart.const import DOMAIN, SPOT_SCAN_INTERVAL
from homeassistant.components.ecosmart.sensor import EcosmartForecastPriceSensor
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import TEST_ICP, load_forecast, load_spot

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SPOT_UNIQUE_ID = f"{TEST_ICP}-spot_price"
FORECAST_UNIQUE_ID = f"{TEST_ICP}-forecast_price"


def _entity_id(entity_registry: er.EntityRegistry, unique_id: str) -> str:
    """Look an entity up by the unique ID the integration assigned it."""
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_all_entities(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test both sensors and their attributes against a snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_device_is_one_service_per_icp(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test each connection point becomes its own service device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_ICP), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.name == TEST_ICP
    assert device.manufacturer == "ecosmart"
    assert device.model == "BOB1101"
    assert device.configuration_url == "https://my.ecosmart.co.nz"


async def test_stale_spot_price_is_unavailable(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an old price is withheld rather than published as current."""
    mock_ecosmart_client.spot.return_value = load_spot("spot_stale.json")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(_entity_id(entity_registry, SPOT_UNIQUE_ID))
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_null_spot_price_is_unavailable(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a fresh observation with no price is unavailable, not zero."""
    mock_ecosmart_client.spot.return_value = replace(
        load_spot("spot_null_prices.json"), is_stale=False
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(_entity_id(entity_registry, SPOT_UNIQUE_ID))
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_empty_forecast_is_unavailable(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an unpublished forecast is a valid empty answer, not an error."""
    mock_ecosmart_client.forecast.return_value = load_forecast("forecast_empty.json")

    await setup_integration(hass, mock_config_entry)

    forecast_state = hass.states.get(_entity_id(entity_registry, FORECAST_UNIQUE_ID))
    assert forecast_state is not None
    assert forecast_state.state == STATE_UNAVAILABLE

    # The spot sensor is unaffected: the two planes fail independently.
    spot_state = hass.states.get(_entity_id(entity_registry, SPOT_UNIQUE_ID))
    assert spot_state is not None
    assert spot_state.state == "0.23"


async def test_negative_forecast_price_passes_through(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a negative wholesale price is published as-is, not clamped."""
    mock_ecosmart_client.forecast.return_value = load_forecast("forecast_negative.json")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(_entity_id(entity_registry, FORECAST_UNIQUE_ID))
    assert state is not None
    assert state.state == "-7.636"
    assert state.attributes["points"][0]["price_dollars_per_mwh"] == -66.4


async def test_coordinator_failure_makes_sensor_unavailable(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed refresh takes the spot sensor down and recovery brings it back."""
    await setup_integration(hass, mock_config_entry)

    spot_entity_id = _entity_id(entity_registry, SPOT_UNIQUE_ID)
    assert hass.states.get(spot_entity_id).state == "0.23"  # type: ignore[union-attr]

    mock_ecosmart_client.spot.side_effect = EcosmartConnectionError("offline")
    freezer.tick(SPOT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(spot_entity_id).state == STATE_UNAVAILABLE  # type: ignore[union-attr]

    # The forecast sensor rides on its own coordinator and is untouched.
    forecast_entity_id = _entity_id(entity_registry, FORECAST_UNIQUE_ID)
    assert hass.states.get(forecast_entity_id).state == "7.636"  # type: ignore[union-attr]

    mock_ecosmart_client.spot.side_effect = None
    freezer.tick(SPOT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(spot_entity_id).state == "0.23"  # type: ignore[union-attr]


@pytest.mark.usefixtures("mock_ecosmart_client")
async def test_forecast_curve_is_not_recorded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the 68-point curve is kept out of the recorder database."""
    await setup_integration(hass, mock_config_entry)

    entity_id = _entity_id(entity_registry, FORECAST_UNIQUE_ID)
    state = hass.states.get(entity_id)
    assert state is not None
    assert len(state.attributes["points"]) == 68
    assert state.attributes["covered_hours"] == 34.0
    assert EcosmartForecastPriceSensor._unrecorded_attributes == frozenset({"points"})
