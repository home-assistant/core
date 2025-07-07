"""Test the Nibe Heat Pump config flow."""

from typing import Any
from unittest.mock import patch

from nibe.heatpump import Model
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import async_add_model


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch(
        "homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.parametrize(
    ("model", "address", "entity_id", "value"),
    [
        (Model.F1255, 49239, "binary_sensor.eb101_installed_49239", "OFF"),
        (Model.F1255, 49239, "binary_sensor.eb101_installed_49239", "ON"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update(
    hass: HomeAssistant,
    model: Model,
    entity_id: str,
    address: int,
    value: Any,
    coils: dict[int, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting of value."""
    coils[address] = value

    await async_add_model(hass, model)

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state == snapshot
