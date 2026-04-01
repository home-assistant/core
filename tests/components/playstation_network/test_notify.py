"""Tests for the PlayStation Network notify platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from psnawp_api.core.psnawp_exceptions import (
    PSNAWPClientError,
    PSNAWPForbiddenError,
    PSNAWPNotFoundError,
    PSNAWPServerError,
)
from psnawp_api.models import User
from psnawp_api.models.group.group import Group
from psnawp_api.models.trophies import TrophySet, TrophySummary
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

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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
@pytest.mark.freeze_time("2025-07-28T00:00:00+00:00")
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
    [
        PSNAWPClientError("error msg"),
        PSNAWPForbiddenError("error msg"),
        PSNAWPNotFoundError("error msg"),
        PSNAWPServerError("error msg"),
    ],
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


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_notify_dynamic_dm_entity_creation_and_removal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test direct messagen otifiers are created and removed dynamically."""
    mock_psnawpapi.me.return_value.get_groups.return_value = []

    fren1 = mock_psnawpapi.user.return_value.friends_list.return_value[0]
    fren2 = MagicMock(spec=User, account_id="fren2-psn-id", online_id="AnotherFren")
    fren2.get_presence.return_value = fren1.get_presence.return_value
    fren2.trophy_summary.return_value = TrophySummary(
        "fren2-psn-id", 420, 20, 5, TrophySet(4782, 1245, 437, 96)
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert len(entity_entries) == 1

    mock_psnawpapi.user.return_value.friends_list.return_value = [fren1, fren2]

    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert len(entity_entries) == 2

    mock_psnawpapi.user.return_value.friends_list.return_value = [fren1]

    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert len(entity_entries) == 1


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_notify_dynamic_group_entity_creation_and_removal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test group notifiers are created and removed dynamically."""
    mock_psnawpapi.user.return_value.friends_list.return_value = []

    group2 = MagicMock(spec=Group, group_id="test-groupid2")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert len(entity_entries) == 1

    mock_psnawpapi.me.return_value.get_groups.return_value.append(group2)

    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert len(entity_entries) == 2

    mock_psnawpapi.me.return_value.get_groups.return_value.pop(1)

    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert len(entity_entries) == 1
