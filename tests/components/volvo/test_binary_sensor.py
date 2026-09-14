"""Test Volvo binary sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.volvo.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    ["ex30_2024", "s90_diesel_2018", "xc40_electric_2024", "xc90_petrol_2019"],
)
async def test_binary_sensor(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await setup_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    [
        "ex30_2024",
        "s90_diesel_2018",
        "xc40_electric_2024",
        "xc60_phev_2020",
        "xc90_petrol_2019",
        "xc90_phev_2024",
    ],
)
async def test_unique_ids(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test binary sensor for unique id's."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await setup_integration()

    assert f"Platform {DOMAIN} does not generate unique IDs" not in caplog.text
