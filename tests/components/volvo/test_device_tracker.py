"""Test Volvo device tracker."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    ["ex30_2024", "s90_diesel_2018", "xc40_electric_2024", "xc90_petrol_2019"],
)
async def test_device_tracker(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device tracker."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.DEVICE_TRACKER]):
        assert await setup_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
