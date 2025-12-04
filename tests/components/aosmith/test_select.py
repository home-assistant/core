"""Tests for the select platform of the A. O. Smith integration."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

from py_aosmith.models import OperationMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.aosmith.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.parametrize(
    ("get_devices_fixture_supports_hot_water_plus"),
    [True],
)
async def test_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the state of the select entity."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("get_devices_fixture_supports_hot_water_plus"),
    [True],
)
@pytest.mark.parametrize(
    ("hass_level", "aosmith_level"),
    [
        ("off", 0),
        ("level1", 1),
        ("level2", 2),
        ("level3", 3),
    ],
)
async def test_set_hot_water_plus_level(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    hass_level: str,
    aosmith_level: int,
) -> None:
    """Test setting the Hot Water+ level."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.my_water_heater_hot_water_plus_level",
            ATTR_OPTION: hass_level,
        },
    )
    await hass.async_block_till_done()

    mock_client.update_mode.assert_called_once_with(
        junction_id="junctionId",
        mode=OperationMode.HEAT_PUMP,
        hot_water_plus_level=aosmith_level,
    )
