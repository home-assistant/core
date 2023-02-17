"""Tests for the diagnostics data provided by the P1 Monitor integration."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "entry": {
            "title": "monitor",
            "data": {
                "host": REDACTED,
            },
        },
        "data": {
            "smartmeter": {
                "gas_consumption": 2273.447,
                "energy_tariff_period": "high",
                "power_consumption": 877,
                "energy_consumption_high": 2770.133,
                "energy_consumption_low": 4988.071,
                "power_production": 0,
                "energy_production_high": 3971.604,
                "energy_production_low": 1432.279,
            },
            "phases": {
                "voltage_phase_l1": "233.6",
                "voltage_phase_l2": "0.0",
                "voltage_phase_l3": "233.0",
                "current_phase_l1": "1.6",
                "current_phase_l2": "4.44",
                "current_phase_l3": "3.51",
                "power_consumed_phase_l1": 315,
                "power_consumed_phase_l2": 0,
                "power_consumed_phase_l3": 624,
                "power_produced_phase_l1": 0,
                "power_produced_phase_l2": 0,
                "power_produced_phase_l3": 0,
            },
            "settings": {
                "gas_consumption_price": "0.64",
                "energy_consumption_price_high": "0.20522",
                "energy_consumption_price_low": "0.20522",
                "energy_production_price_high": "0.20522",
                "energy_production_price_low": "0.20522",
            },
            "watermeter": {
                "consumption_day": 112.0,
                "consumption_total": 1696.14,
                "pulse_count": 112.0,
            },
        },
    }
