"""Tests for EMHASS runtime payload generation."""

from datetime import UTC, datetime, timedelta

import pytest

from homeassistant.components.photoptimizer.emhass_client import EmhassClient
from homeassistant.components.photoptimizer.models import (
    OptimizationBucket,
    OptimizationInputs,
)
from homeassistant.core import HomeAssistant


def _build_inputs() -> OptimizationInputs:
    """Create deterministic optimization inputs for payload assertions."""
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    return OptimizationInputs(
        timeline=[
            OptimizationBucket(start=start, price=0.21, pv=1.4, load=0.8),
            OptimizationBucket(
                start=start + timedelta(hours=1),
                price=0.23,
                pv=1.1,
                load=0.7,
            ),
        ],
        battery_soc=0.42,
    )


async def test_runtimeparams_include_explicit_battery_config(
    hass: HomeAssistant,
) -> None:
    """Ensure battery mode and key plant params are always sent to EMHASS."""
    client = EmhassClient(
        hass,
        "http://192.168.1.104:5000",
        battery_capacity_kwh=12.5,
        battery_efficiency=0.81,
        battery_soc_reserve=0.2,
        wear_cost_per_kwh=0.0,
    )

    runtimeparams = client._build_runtimeparams(_build_inputs())

    assert runtimeparams["set_use_pv"] is True
    assert runtimeparams["set_use_battery"] is True
    assert runtimeparams["battery_discharge_power_max"] == pytest.approx(1000.0)
    assert runtimeparams["battery_charge_power_max"] == pytest.approx(1000.0)
    assert runtimeparams["battery_nominal_energy_capacity"] == pytest.approx(12500.0)
    assert runtimeparams["battery_charge_efficiency"] == pytest.approx(0.81)
    assert runtimeparams["battery_discharge_efficiency"] == pytest.approx(0.81)
    assert runtimeparams["battery_minimum_state_of_charge"] == pytest.approx(0.2)
    assert runtimeparams["battery_maximum_state_of_charge"] == pytest.approx(0.9)
    assert runtimeparams["soc_init"] == pytest.approx(0.42)
    assert runtimeparams["soc_final"] == pytest.approx(0.42)
    assert runtimeparams["battery_target_state_of_charge"] == pytest.approx(0.42)


async def test_runtimeparams_clamp_battery_defaults(hass: HomeAssistant) -> None:
    """Ensure invalid battery settings are normalized before sending runtimeparams."""
    client = EmhassClient(
        hass,
        "http://192.168.1.104:5000",
        battery_capacity_kwh=0,
        battery_efficiency=1.2,
        battery_soc_reserve=0.2,
        wear_cost_per_kwh=1.5,
    )

    runtimeparams = client._build_runtimeparams(_build_inputs())

    assert runtimeparams["battery_nominal_energy_capacity"] == pytest.approx(5000.0)
    assert runtimeparams["battery_charge_efficiency"] == pytest.approx(1.0)
    assert runtimeparams["battery_discharge_efficiency"] == pytest.approx(1.0)
    assert runtimeparams["weight_battery_charge"] == pytest.approx(1.5)
    assert runtimeparams["weight_battery_discharge"] == pytest.approx(1.5)
