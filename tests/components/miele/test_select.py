"""Tests for miele select module."""

from unittest.mock import MagicMock, Mock

from aiohttp import ClientResponseError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

TEST_PLATFORM = SELECT_DOMAIN
pytestmark = [
    pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)]),
    pytest.mark.parametrize(
        "load_action_file", ["action_freezer.json"], ids=["freezer"]
    ),
]

ENTITY_ID = "select.freezer_mode"


async def test_select_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test select entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


async def test_selecting(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
) -> None:
    """Test the select service."""

    await hass.services.async_call(
        TEST_PLATFORM,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "sabbath"},
        blocking=True,
    )
    mock_miele_client.send_action.assert_called_once()


async def test_api_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.send_action.side_effect = ClientResponseError(Mock(), Mock())

    with pytest.raises(
        HomeAssistantError, match=f"Failed to set state for {ENTITY_ID}"
    ):
        await hass.services.async_call(
            TEST_PLATFORM,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "sabbath"},
            blocking=True,
        )
    mock_miele_client.send_action.assert_called_once()


async def test_invalid_option(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.send_action.side_effect = ClientResponseError(Mock(), Mock())

    with pytest.raises(
        ServiceValidationError, match=f'Invalid option: "normal" on {ENTITY_ID}'
    ):
        await hass.services.async_call(
            TEST_PLATFORM,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "normal"},
            blocking=True,
        )
    mock_miele_client.send_action.assert_not_called()
