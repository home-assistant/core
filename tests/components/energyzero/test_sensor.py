"""Tests for the sensors provided by the EnergyZero integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from energyzero import EnergyZeroNoDataError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energyzero.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = [pytest.mark.freeze_time("2026-04-10 20:32:59")]


async def test_sensor(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the EnergyZero - Energy sensors."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    with patch("homeassistant.components.energyzero.PLATFORMS", ["sensor"]):
        await setup_integration(hass, mock_config_entry)

    gas_state = hass.states.get("sensor.energyzero_today_gas_current_hour_price")
    assert gas_state
    assert gas_state.state == "0.5468407201224"

    energy_state = hass.states.get("sensor.energyzero_today_energy_current_hour_price")
    assert energy_state
    assert energy_state.state == "0.17191075"

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_energyzero")
@pytest.mark.parametrize(
    "key",
    ["current_hour_price", "next_hour_price", "hours_priced_equal_or_lower"],
)
async def test_existing_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    key: str,
) -> None:
    """Test existing sensors retain their registry entries and customized entity IDs."""
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        "sensor",
        "energyzero",
        f"{mock_config_entry.entry_id}_today_energy_{key}",
        suggested_object_id=f"custom_{key}",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entry.entity_id) is not None
    assert (updated_entry := entity_registry.async_get(entry.entity_id))
    assert updated_entry.id == entry.id
    assert updated_entry.unique_id == entry.unique_id
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 11
    )


async def test_sensor_ignores_missing_tomorrow_prices(
    hass: HomeAssistant,
    mock_energyzero: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test missing tomorrow prices do not prevent sensor setup."""
    original_side_effect = mock_energyzero.get_electricity_prices.side_effect
    tomorrow = dt_util.now().date() + timedelta(days=1)

    def _get_electricity_prices(*args, **kwargs):
        if kwargs["start_date"] == tomorrow:
            raise EnergyZeroNoDataError
        return original_side_effect(*args, **kwargs)

    mock_energyzero.get_electricity_prices.side_effect = _get_electricity_prices

    with patch("homeassistant.components.energyzero.PLATFORMS", ["sensor"]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.energyzero_today_energy_current_hour_price")


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "entity_id", "expected_state"),
    [
        (
            "get_gas_prices",
            "sensor.energyzero_today_gas_current_hour_price",
            STATE_UNKNOWN,
        ),
        (
            "get_electricity_prices",
            "sensor.energyzero_today_energy_current_hour_price",
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_no_data(
    hass: HomeAssistant,
    mock_energyzero: MagicMock,
    freezer: FrozenDateTimeFactory,
    service: str,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test the EnergyZero - No data available scenarios."""
    getattr(mock_energyzero, service).side_effect = EnergyZeroNoDataError

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == expected_state
