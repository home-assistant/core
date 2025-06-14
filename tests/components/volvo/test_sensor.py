"""Test Volvo sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import model

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "",
    [
        pytest.param(marks=model("xc40_electric_2024")),
        pytest.param(marks=model("s90_diesel_2018")),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
