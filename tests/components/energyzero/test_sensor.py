"""Tests for the sensors provided by the EnergyZero integration."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from energyzero import EnergyZeroNoDataError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energyzero.const import (
    CONF_ELECTRICITY_PRICE_INTERVAL,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

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
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_energyzero")
@pytest.mark.parametrize("disabled_by", [None, er.RegistryEntryDisabler.USER])
async def test_existing_market_registry_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Keep existing identities and user customizations through setup and reload."""
    mock_config_entry.add_to_hass(hass)
    entries = [
        entity_registry.async_get_or_create(
            "sensor",
            "energyzero",
            f"12345_today_energy_{key}",
            suggested_object_id=f"custom_{key}",
            config_entry=mock_config_entry,
            disabled_by=disabled_by,
        )
        for key in (
            "current_hour_price",
            "next_hour_price",
            "average_price",
            "min_price",
            "max_price",
            "highest_price_time",
            "lowest_price_time",
            "percentage_of_max",
            "hours_priced_equal_or_lower",
        )
    ]
    entries = [
        entity_registry.async_update_entity(
            entry.entity_id, name=f"Custom {entry.entity_id}"
        )
        for entry in entries
    ]
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ELECTRICITY_PRICE_INTERVAL: "quarter_hourly"}
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for original in entries:
        assert (entry := entity_registry.async_get(original.entity_id))
        assert entry.id == original.id
        assert entry.entity_id == original.entity_id
        assert entry.unique_id == original.unique_id
        assert entry.name == original.name
        assert entry.disabled_by == original.disabled_by
    assert len(er.async_entries_for_config_entry(entity_registry, "12345")) == 16


@pytest.mark.parametrize(
    ("moment", "current", "next_hour"),
    [
        pytest.param(
            "2026-04-10T00:00:00+02:00",
            "0.54345990633176",
            "0.54345990633176",
            id="midnight",
        ),
        pytest.param(
            "2026-04-10T05:00:00+02:00",
            "0.54345990633176",
            "0.5468407201224",
            id="next-hour-boundary",
        ),
        pytest.param(
            "2026-04-10T05:59:59+02:00",
            "0.54345990633176",
            "0.5468407201224",
            id="before-boundary",
        ),
        pytest.param(
            "2026-04-10T06:00:00+02:00",
            "0.5468407201224",
            "0.5468407201224",
            id="boundary",
        ),
    ],
)
async def test_gas_prices_after_fresh_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    moment: str,
    current: str,
    next_hour: str,
) -> None:
    """Exercise actual REST parsing without a remembered sensor value."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(moment)
    electricity = await async_load_json_object_fixture(
        hass, "today_energy.json", DOMAIN
    )
    gas = await async_load_json_object_fixture(hass, "today_gas.json", DOMAIN)
    mock_config_entry.add_to_hass(hass)
    with patch(
        "energyzero.api.rest.RESTClient._request",
        side_effect=[electricity, gas, electricity],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.energyzero_today_gas_current_hour_price"))
    assert state.state == current
    assert (state := hass.states.get("sensor.energyzero_today_gas_next_hour_price"))
    assert state.state == next_hour


@pytest.mark.parametrize(
    ("block_count", "expected"),
    [
        pytest.param(2, "0.5468407201224", id="new-price"),
        pytest.param(1, STATE_UNKNOWN, id="missing-price"),
    ],
)
async def test_gas_price_expires_at_boundary(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    block_count: int,
    expected: str,
) -> None:
    """A refresh must select the new interval or report an unknown price."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(datetime(2026, 4, 10, 5, 55, tzinfo=ZoneInfo("Europe/Amsterdam")))
    electricity = await async_load_json_object_fixture(
        hass, "today_energy.json", DOMAIN
    )
    gas = await async_load_json_object_fixture(hass, "today_gas.json", DOMAIN)
    gas = {
        **gas,
        **{
            stream: gas[stream][:block_count]
            for stream in ("base", "base_with_vat", "all_in", "all_in_with_vat")
        },
    }
    mock_config_entry.add_to_hass(hass)
    with patch(
        "energyzero.api.rest.RESTClient._request", side_effect=[electricity, gas] * 2
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert (
            state := hass.states.get("sensor.energyzero_today_gas_current_hour_price")
        )
        assert state.state == "0.54345990633176"
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get("sensor.energyzero_today_gas_current_hour_price"))
    assert state.state == expected


async def test_gas_price_survives_calendar_rollover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Refreshing for a new calendar date keeps the still-valid gas interval."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-04-09T23:55:00+02:00")
    electricity = await async_load_json_object_fixture(
        hass, "today_energy.json", DOMAIN
    )
    gas = await async_load_json_object_fixture(hass, "today_gas.json", DOMAIN)
    mock_config_entry.add_to_hass(hass)
    with patch(
        "energyzero.api.rest.RESTClient._request",
        side_effect=[electricity, gas, electricity] * 2,
    ) as request:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert (
            state := hass.states.get("sensor.energyzero_today_gas_current_hour_price")
        )
        assert state.state == "0.54345990633176"
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert request.await_args_list[1].kwargs["params"]["date"] == "09-04-2026"
    assert request.await_args_list[4].kwargs["params"]["date"] == "10-04-2026"
    assert (state := hass.states.get("sensor.energyzero_today_gas_current_hour_price"))
    assert state.state == "0.54345990633176"
