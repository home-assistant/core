"""Tests for the ntfy event platform."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from aiontfy import Event
from aiontfy.exceptions import (
    NtfyConnectionError,
    NtfyForbiddenError,
    NtfyHTTPError,
    NtfyTimeoutError,
    NtfyUnauthorizedAuthenticationError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ntfy.const import CONF_TOPIC, DOMAIN, SUBENTRY_TYPE_TOPIC
from homeassistant.config_entries import (
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigSubentryData,
)
from homeassistant.const import (
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

TOPIC_PROTECTED_ISSUE_ID = "topic_protected_123456789_ABCDEF"
OTHER_TOPIC_PROTECTED_ISSUE_ID = "topic_protected_987654321_GHIJKL"


@pytest.fixture
def other_config_entry() -> MockConfigEntry:
    """Mock a second ntfy config entry subscribing to the same topic."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ntfy.example.com",
        data={
            CONF_URL: "https://ntfy.example.com/",
            CONF_USERNAME: None,
            CONF_TOKEN: "token",
            CONF_VERIFY_SSL: True,
        },
        entry_id="987654321",
        subentries_data=[
            ConfigSubentryData(
                data={CONF_TOPIC: "mytopic"},
                subentry_id="GHIJKL",
                subentry_type=SUBENTRY_TYPE_TOPIC,
                title="mytopic",
                unique_id="mytopic",
            )
        ],
    )


async def _setup_protected_topic_on_two_entries(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    other_config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Set up two config entries failing to subscribe to the same topic."""
    mock_aiontfy.subscribe.side_effect = NtfyForbiddenError(403, 403, "forbidden")
    config_entry.add_to_hass(hass)
    other_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, "repairs", {})
    # Sets up both entries
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def event_only() -> AsyncGenerator[None]:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.ntfy.PLATFORMS",
        [Platform.EVENT],
    ):
        yield


@pytest.mark.usefixtures("mock_aiontfy")
@pytest.mark.freeze_time("2025-09-03T22:00:00.000Z")
async def test_event_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the ntfy event platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("mock_aiontfy")
async def test_event(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test ntfy events."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("event.mytopic"))
    assert state.state != STATE_UNKNOWN

    assert state.attributes == {
        "actions": [],
        "attachment": None,
        "click": "https://example.com/",
        "content_type": None,
        "entity_picture": "https://example.com/icon.png",
        "event": Event.MESSAGE,
        "event_type": "Title: Hello",
        "event_types": [
            "Title: Hello",
        ],
        "expires": datetime(2025, 3, 29, 5, 58, 46, tzinfo=UTC),
        "friendly_name": "mytopic",
        "icon": "https://example.com/icon.png",
        "id": "h6Y2hKA5sy0U",
        "message": "Hello",
        "priority": 3,
        "tags": [
            "octopus",
        ],
        "time": datetime(2025, 3, 28, 17, 58, 46, tzinfo=UTC),
        "title": "Title",
        "topic": "mytopic",
        "sequence_id": "Mc3otamDNcpJ",
    }


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (
            NtfyHTTPError(41801, 418, "I'm a teapot", ""),
            STATE_UNAVAILABLE,
        ),
        (
            NtfyConnectionError,
            STATE_UNAVAILABLE,
        ),
        (
            NtfyTimeoutError,
            STATE_UNAVAILABLE,
        ),
        (
            NtfyUnauthorizedAuthenticationError(40101, 401, "unauthorized"),
            STATE_UNAVAILABLE,
        ),
        (
            NtfyForbiddenError(403, 403, "forbidden"),
            STATE_UNAVAILABLE,
        ),
        (
            asyncio.CancelledError,
            STATE_UNAVAILABLE,
        ),
        (
            asyncio.InvalidStateError,
            STATE_UNKNOWN,
        ),
        (
            ValueError,
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_event_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
    expected_state: str,
) -> None:
    """Test ntfy events exceptions."""
    mock_aiontfy.subscribe.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("event.mytopic"))
    assert state.state == expected_state


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("event.mytopic", id="not_renamed"),
        pytest.param("event.renamed", id="renamed"),
    ],
)
async def test_event_topic_protected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    hass_client: ClientSessionGenerator,
    entity_id: str,
) -> None:
    """Test ntfy events cannot subscribe to protected topic."""
    mock_aiontfy.subscribe.side_effect = NtfyForbiddenError(403, 403, "forbidden")

    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, "repairs", {})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("event.mytopic"))
    assert state.state == STATE_UNAVAILABLE

    assert (
        issue := issue_registry.async_get_issue(
            domain=DOMAIN, issue_id=TOPIC_PROTECTED_ISSUE_ID
        )
    )
    assert issue.config_entry_id == config_entry.entry_id
    assert issue.config_subentry_id == "ABCDEF"
    assert issue.translation_placeholders == {"topic": "mytopic", "name": "ntfy.sh"}

    # The repair flow disables the entity also if it was renamed after the issue
    entity_registry.async_update_entity("event.mytopic", new_entity_id=entity_id)
    await hass.async_block_till_done()

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, TOPIC_PROTECTED_ISSUE_ID)

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"topic": "mytopic", "name": "ntfy.sh"}

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"

    assert (entity := entity_registry.async_get(entity_id))
    assert entity.disabled
    assert entity.disabled_by is er.RegistryEntryDisabler.USER


async def test_event_topic_protected_per_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    other_config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the same protected topic on two config entries gets separate issues."""
    await _setup_protected_topic_on_two_entries(
        hass, config_entry, other_config_entry, mock_aiontfy, freezer
    )

    assert (issue := issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID))
    assert issue.config_entry_id == config_entry.entry_id
    assert issue.translation_placeholders == {"topic": "mytopic", "name": "ntfy.sh"}
    assert (
        other_issue := issue_registry.async_get_issue(
            DOMAIN, OTHER_TOPIC_PROTECTED_ISSUE_ID
        )
    )
    assert other_issue.config_entry_id == other_config_entry.entry_id
    assert other_issue.config_subentry_id == "GHIJKL"
    assert other_issue.translation_placeholders == {
        "topic": "mytopic",
        "name": "ntfy.example.com",
    }

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)
    assert issue_registry.async_get_issue(DOMAIN, OTHER_TOPIC_PROTECTED_ISSUE_ID)


async def test_event_topic_protected_fix_flow_per_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    other_config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the fix flow only disables the entity of the entry owning the issue."""
    await _setup_protected_topic_on_two_entries(
        hass, config_entry, other_config_entry, mock_aiontfy, freezer
    )

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, OTHER_TOPIC_PROTECTED_ISSUE_ID)
    assert result["description_placeholders"] == {
        "topic": "mytopic",
        "name": "ntfy.example.com",
    }
    result = await process_repair_fix_flow(client, result["flow_id"])
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    assert (entity := entity_registry.async_get("event.mytopic"))
    assert entity.config_entry_id == config_entry.entry_id
    assert not entity.disabled
    assert (other_entity := entity_registry.async_get("event.mytopic_2"))
    assert other_entity.config_entry_id == other_config_entry.entry_id
    assert other_entity.disabled_by is er.RegistryEntryDisabler.USER

    assert issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)
    assert not issue_registry.async_get_issue(DOMAIN, OTHER_TOPIC_PROTECTED_ISSUE_ID)


@pytest.mark.usefixtures("mock_aiontfy")
async def test_event_topic_protected_issue_deleted_on_subscribe(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the protected topic issue is deleted once subscribing succeeds."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        TOPIC_PROTECTED_ISSUE_ID,
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="topic_protected",
        translation_placeholders={"topic": "mytopic", "name": "ntfy.sh"},
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)


async def test_event_topic_protected_issue_deleted_on_remove(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the protected topic issue is deleted when the topic is removed."""
    mock_aiontfy.subscribe.side_effect = NtfyForbiddenError(403, 403, "forbidden")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)

    assert hass.config_entries.async_remove_subentry(config_entry, "ABCDEF")
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert not issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)


async def test_event_topic_protected_issue_deleted_on_remove_not_loaded(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the protected topic issue is deleted with the topic of an unloaded entry."""
    mock_aiontfy.subscribe.side_effect = NtfyForbiddenError(403, 403, "forbidden")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)

    assert hass.config_entries.async_remove_subentry(config_entry, "ABCDEF")
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)


async def _disable_entity(hass: HomeAssistant) -> None:
    """Disable the event entity."""
    er.async_get(hass).async_update_entity(
        "event.mytopic", disabled_by=er.RegistryEntryDisabler.USER
    )


async def _disable_device(hass: HomeAssistant) -> None:
    """Disable the device of the event entity."""
    assert (entity := er.async_get(hass).async_get("event.mytopic"))
    assert entity.device_id
    dr.async_get(hass).async_update_device(
        entity.device_id, disabled_by=dr.DeviceEntryDisabler.USER
    )


async def _remove_entity(hass: HomeAssistant) -> None:
    """Remove the event entity from the entity registry."""
    er.async_get(hass).async_remove("event.mytopic")


@pytest.mark.parametrize(
    "remove_entity",
    [
        pytest.param(_disable_entity, id="entity_disabled"),
        pytest.param(_disable_device, id="device_disabled"),
        pytest.param(_remove_entity, id="entity_removed"),
    ],
)
async def test_event_topic_protected_issue_deleted_on_entity_disable_or_remove(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    remove_entity: Callable[[HomeAssistant], Coroutine[None, None, None]],
) -> None:
    """Test the issue is deleted when the entity is disabled or removed."""
    mock_aiontfy.subscribe.side_effect = NtfyForbiddenError(403, 403, "forbidden")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)

    await remove_entity(hass)
    await hass.async_block_till_done()

    assert "ABCDEF" in config_entry.subentries
    assert hass.states.get("event.mytopic") is None
    assert not issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)


async def _reload_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Reload the config entry."""
    assert await hass.config_entries.async_reload(config_entry.entry_id)


async def _disable_and_enable_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Disable and re-enable the config entry."""
    assert await hass.config_entries.async_set_disabled_by(
        config_entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    # Core hides the issue of the disabled entry instead of it being deleted
    assert (
        issue := ir.async_get(hass).async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)
    )
    assert issue.dismissed_version is not None
    assert await hass.config_entries.async_set_disabled_by(config_entry.entry_id, None)


@pytest.mark.parametrize(
    "reload_entry",
    [
        pytest.param(_reload_entry, id="reload"),
        pytest.param(_disable_and_enable_entry, id="disable_enable"),
    ],
)
async def test_event_topic_protected_issue_ignore_kept_on_reload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    reload_entry: Callable[
        [HomeAssistant, MockConfigEntry], Coroutine[None, None, None]
    ],
) -> None:
    """Test an ignored protected topic issue stays ignored when the entry reloads."""
    mock_aiontfy.subscribe.side_effect = NtfyForbiddenError(403, 403, "forbidden")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    ir.async_ignore_issue(hass, DOMAIN, TOPIC_PROTECTED_ISSUE_ID, True)

    await reload_entry(hass, config_entry)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (issue := issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID))
    assert issue.config_entry_id == config_entry.entry_id
    assert issue.config_subentry_id == "ABCDEF"
    assert issue.dismissed_version is not None
    assert mock_aiontfy.subscribe.call_count == 2


@pytest.mark.parametrize(
    "disable_entity",
    [
        pytest.param(_disable_entity, id="entity_disabled"),
        pytest.param(_disable_device, id="device_disabled"),
    ],
)
async def test_event_topic_protected_issue_deleted_on_disable_while_entry_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    disable_entity: Callable[[HomeAssistant], Coroutine[None, None, None]],
) -> None:
    """Test the issue is deleted if the entity is disabled while the entry is."""
    mock_aiontfy.subscribe.side_effect = NtfyForbiddenError(403, 403, "forbidden")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_set_disabled_by(
        config_entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)

    await disable_entity(hass)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)

    assert await hass.config_entries.async_set_disabled_by(config_entry.entry_id, None)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("event.mytopic") is None
    assert not issue_registry.async_get_issue(DOMAIN, TOPIC_PROTECTED_ISSUE_ID)
