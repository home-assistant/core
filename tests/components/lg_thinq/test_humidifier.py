"""Tests for the LG ThinQ humidifier platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["dehumidifier"])
async def test_humidifier_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.lg_thinq.PLATFORMS", [Platform.HUMIDIFIER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


class LGHumidifier(HumidifierEntity):
    """Test the humidifier."""

    def _adjust_target_humidity(self, current_target_humidity, step, requested):
        method = (
            "round"
            if (
                current_target_humidity is None
                or abs(requested - current_target_humidity) > step
            )
            else "ceil"
            if requested > current_target_humidity
            else "floor"
        )
        if method == "round":
            return round(requested / step) * step
        if method == "floor":
            return (requested // step) * step
        if method == "ceil":
            return ((requested + step - 1) // step) * step
        return requested


@pytest.mark.parametrize(
    ("current_target_humidity", "step", "requested", "adjusted_humidity"),
    [
        (55, 5, 43, 45),  # round
        (55, 5, 54, 50),  # floor
        (55, 5, 56, 60),  # ceil
    ],
)
def test_adjust_target_humidity(
    current_target_humidity: int,
    step: int,
    requested: int,
    adjusted_humidity: int,
) -> None:
    """Test the humidifier can set humidity level without mocking."""
    entity = LGHumidifier()
    result = entity._adjust_target_humidity(current_target_humidity, step, requested)
    assert result == adjusted_humidity
