"""Test Volvo sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import model


@pytest.mark.parametrize(
    ("keys"),
    [
        pytest.param(
            [
                "battery_charge_level",
                "car_connection",
                "charging_connection_status",
                "distance_to_empty_battery",
                "distance_to_service",
                "engine_time_to_service",
                "est_charging_time",
                "odometer",
                "time_to_service",
                "tm_avg_energy_consumption",
                "tm_avg_speed",
                "tm_distance",
            ],
            marks=model("xc40_electric_2024"),
        ),
        pytest.param(
            [
                "car_connection",
                "distance_to_empty_tank",
                "distance_to_service",
                "engine_time_to_service",
                "fuel_amount",
                "odometer",
                "time_to_service",
                "tm_avg_fuel_consumption",
                "tm_avg_speed",
                "tm_distance",
            ],
            marks=model("s90_diesel_2018"),
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
    model_from_marker: str,
    keys: list[str],
    snapshot: SnapshotAssertion,
) -> None:
    """Test time to service."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

        for key in keys:
            entity_id = f"sensor.volvo_{model_from_marker}_{key}"

            state = hass.states.get(entity_id)
            assert state, f"No state found for {entity_id}"

            entry = entity_registry.async_get(entity_id)
            assert entry, f"No entry found for {entity_id}"

            assert (state.state, state.attributes, entry.unique_id) == snapshot, (
                f"Snapshot does not match for {entity_id}"
            )
