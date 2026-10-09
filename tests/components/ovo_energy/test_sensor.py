"""Tests for OVO Energy sensors."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from ovoenergy.models import (
    OVOCost,
    OVODailyElectricity,
    OVODailyGas,
    OVODailyUsage,
    OVOInterval,
)
import pytest

from homeassistant.components.ovo_energy.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

INTERVAL = OVOInterval(
    start=datetime(2026, 9, 1, tzinfo=UTC),
    end=datetime(2026, 9, 2, tzinfo=UTC),
)
USAGE = OVODailyUsage(
    electricity=[
        OVODailyElectricity(
            consumption=0,
            interval=INTERVAL,
            meter_readings=None,
            has_half_hour_data=False,
            cost=OVOCost(amount=0, currency_unit="GBP"),
            rates=None,
        )
    ],
    gas=[
        OVODailyGas(
            consumption=6.96,
            volume=None,
            interval=INTERVAL,
            meter_readings=None,
            has_half_hour_data=False,
            cost=OVOCost(amount=0.42, currency_unit="GBP"),
            rates=None,
        )
    ],
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("fuel", ["gas", "electricity"])
@pytest.mark.parametrize("missing_usage", [pytest.param([], id="empty"), None])
async def test_missing_usage_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fuel: str,
    missing_usage: list[OVODailyElectricity | OVODailyGas] | None,
) -> None:
    """Sensors recover after their fuel's usage disappears during an update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "example@example.com", CONF_PASSWORD: "password"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ovo_energy.OVOEnergy.authenticate",
            return_value=True,
        ),
        patch("homeassistant.components.ovo_energy.OVOEnergy.bootstrap_accounts"),
        patch("homeassistant.components.ovo_energy.OVOEnergy.account_id", "123456"),
        patch("homeassistant.components.ovo_energy.OVOEnergy.username", "Example"),
        patch(
            "homeassistant.components.ovo_energy.OVOEnergy.get_daily_usage",
            return_value=USAGE,
        ) as mock_usage,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        expected = {
            "sensor.example_last_electricity_reading": "0",
            "sensor.example_last_electricity_cost": "0",
            "sensor.example_last_electricity_start_time": "2026-09-01T00:00:00+00:00",
            "sensor.example_last_electricity_end_time": "2026-09-02T00:00:00+00:00",
            "sensor.example_last_gas_reading": "6.96",
            "sensor.example_last_gas_cost": "0.42",
            "sensor.example_last_gas_start_time": "2026-09-01T00:00:00+00:00",
            "sensor.example_last_gas_end_time": "2026-09-02T00:00:00+00:00",
        }
        assert {
            state.entity_id: state.state for state in hass.states.async_all("sensor")
        } == expected

        mock_usage.return_value = replace(USAGE, **{fuel: missing_usage})
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        missing_states = {
            f"sensor.example_last_{fuel}_{suffix}": STATE_UNKNOWN
            for suffix in ("reading", "cost", "start_time", "end_time")
        }
        assert {
            state.entity_id: state.state for state in hass.states.async_all("sensor")
        } == expected | missing_states

        mock_usage.return_value = USAGE
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert {
            state.entity_id: state.state for state in hass.states.async_all("sensor")
        } == expected
