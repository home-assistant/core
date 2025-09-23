"""Tests for the PlayStation Network notify platform."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

from freezegun.api import freeze_time
from psnawp_api.core.psnawp_exceptions import (
    PSNAWPClientError,
    PSNAWPForbiddenError,
    PSNAWPNotFoundError,
    PSNAWPServerError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.playstation_network.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def notify_only() -> AsyncGenerator[None]:
    """Enable only the notify platform."""
    with patch(
        "homeassistant.components.playstation_network.PLATFORMS",
        [Platform.NOTIFY],
    ):
        yield


@pytest.mark.usefixtures("mock_psnawpapi", "entity_registry_enabled_by_default")
async def test_notify_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the notify platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "entity_id",
    [
        "notify.testuser_group_publicuniversalfriend",
        "notify.testuser_direct_message_publicuniversalfriend",
    ],
)
@freeze_time("2025-07-28T00:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    entity_id: str,
) -> None:
    """Test send message."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MESSAGE: "henlo fren",
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2025-07-28T00:00:00+00:00"
    mock_psnawpapi.group.return_value.send_message.assert_called_once_with("henlo fren")


@pytest.mark.parametrize(
    "exception",
    [PSNAWPClientError, PSNAWPForbiddenError, PSNAWPNotFoundError, PSNAWPServerError],
)
async def test_send_message_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
) -> None:
    """Test send message exceptions."""

    mock_psnawpapi.group.return_value.send_message.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("notify.testuser_group_publicuniversalfriend")
    assert state
    assert state.state == STATE_UNKNOWN

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.testuser_group_publicuniversalfriend",
                ATTR_MESSAGE: "henlo fren",
            },
            blocking=True,
        )

    mock_psnawpapi.group.return_value.send_message.assert_called_once_with("henlo fren")


async def test_notify_skip_forbidden(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we skip creation of notifiers if forbidden by parental controls."""

    mock_psnawpapi.me.return_value.get_groups.side_effect = PSNAWPForbiddenError(
        """{"error": {"message": "Not permitted by parental control"}}"""
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("notify.testuser_group_publicuniversalfriend")
    assert state is None

    assert issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=f"group_chat_forbidden_{config_entry.entry_id}"
    )
