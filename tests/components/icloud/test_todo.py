"""Tests for the iCloud to-do platform."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyicloud.services.reminders.client import RemindersApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.icloud.coordinator import (
    REMINDERS_SCAN_INTERVAL,
    UNDECODED_TITLE,
)
from homeassistant.components.todo import (
    ATTR_DESCRIPTION,
    ATTR_DUE_DATE,
    ATTR_DUE_DATETIME,
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoServices,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import (
    AsyncMock,
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)

ENTITY_ID = "todo.test_icloud_account_groceries"


def _reminder(
    uid: str,
    title: str,
    *,
    completed: bool = False,
    parent: str | None = None,
    due: datetime | None = None,
    desc: str = "",
) -> MagicMock:
    """Build a mock pyicloud reminder."""
    reminder = MagicMock()
    reminder.id = uid
    reminder.title = title
    reminder.desc = desc
    reminder.due_date = due
    reminder.all_day = False
    reminder.completed = completed
    reminder.completed_date = datetime(2024, 1, 2, 3, 4) if completed else None
    reminder.parent_reminder_id = parent
    reminder.deleted = False
    return reminder


def _list(list_id: str, title: str, *, is_group: bool = False) -> MagicMock:
    """Build a mock pyicloud reminder list."""
    reminder_list = MagicMock()
    reminder_list.id = list_id
    reminder_list.title = title
    reminder_list.is_group = is_group
    reminder_list.deleted = False
    return reminder_list


@pytest.fixture(name="reminders")
def mock_reminders(icloud_client: AsyncMock) -> MagicMock:
    """Mock the reminders service with one list."""
    service = icloud_client.api.reminders
    service.lists.return_value = [_list("list1", "Groceries")]
    service.list_reminders.return_value = MagicMock(
        reminders=[
            _reminder("r1", "Milk"),
            _reminder("r2", "Bread", completed=True),
        ]
    )
    return service


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the config entry with only the to-do platform loaded."""
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.icloud.PLATFORMS", [Platform.TODO]):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a reminder list becomes a to-do entity with its items."""
    await _setup(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_groups_skipped(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test that reminder groups do not become entities.

    A group and a list inside it can share a name, which would otherwise
    create two identically named entities, one of them always empty.
    """
    reminders.lists.return_value = [
        _list("list1", "Groceries"),
        _list("list2", "Family", is_group=True),
    ]

    await _setup(hass, config_entry)

    assert hass.states.get(ENTITY_ID) is not None
    assert hass.states.get("todo.test_icloud_account_family") is None


async def test_subtasks_follow_their_parent(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test that a subtask is ordered directly after its parent."""
    reminders.list_reminders.return_value = MagicMock(
        reminders=[
            _reminder("r1", "Child", parent="r2"),
            _reminder("r2", "Parent"),
            _reminder("r3", "Other"),
        ]
    )

    await _setup(hass, config_entry)

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    summaries = [item["summary"] for item in result[ENTITY_ID]["items"]]
    assert summaries == ["Parent", "Child", "Other"]


async def test_create_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test creating a reminder."""
    await _setup(hass, config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ITEM: "Eggs",
            ATTR_DUE_DATE: date(2024, 5, 1),
            ATTR_DESCRIPTION: "a dozen",
        },
        blocking=True,
    )

    reminders.create.assert_called_once_with(
        list_id="list1",
        title="Eggs",
        desc="a dozen",
        due_date=datetime(2024, 5, 1),
        all_day=True,
    )


async def test_update_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test renaming and completing a reminder."""
    existing = _reminder("r1", "Milk")
    reminders.get.return_value = existing

    await _setup(hass, config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ITEM: "Milk",
            ATTR_RENAME: "Oat milk",
            ATTR_STATUS: "completed",
        },
        blocking=True,
    )

    assert existing.title == "Oat milk"
    assert existing.completed is True
    reminders.update.assert_called_once_with(existing)


async def test_delete_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test deleting a reminder."""
    existing = _reminder("r1", "Milk")
    reminders.get.return_value = existing

    await _setup(hass, config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: "Milk"},
        blocking=True,
    )

    reminders.delete.assert_called_once_with(existing)


async def test_partial_delete_still_refreshes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test that a batch failing halfway still refreshes the list.

    The reminders deleted before the failure are already gone in iCloud, so
    leaving them on screen until the next poll would be wrong.
    """
    reminders.list_reminders.return_value = MagicMock(
        reminders=[_reminder("r1", "Milk"), _reminder("r2", "Eggs")]
    )
    reminders.delete.side_effect = [None, RemindersApiError("boom")]

    await _setup(hass, config_entry)
    before = reminders.list_reminders.call_count

    with pytest.raises(HomeAssistantError, match="Error updating reminders"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: ["Milk", "Eggs"]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert reminders.delete.call_count == 2
    assert reminders.list_reminders.call_count > before


async def test_api_error_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test that an iCloud error surfaces as a Home Assistant error."""
    reminders.get.side_effect = RemindersApiError("boom")

    await _setup(hass, config_entry)

    with pytest.raises(HomeAssistantError, match="Error updating reminders"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: "Milk"},
            blocking=True,
        )


async def test_new_list_added_on_later_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a list created after setup appears on a later refresh."""
    await _setup(hass, config_entry)
    assert hass.states.get("todo.test_icloud_account_travel") is None

    reminders.lists.return_value = [
        _list("list1", "Groceries"),
        _list("list2", "Travel"),
    ]
    freezer.tick(REMINDERS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # The scheduled refresh runs as a background task of the config entry.
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("todo.test_icloud_account_travel") is not None


async def test_create_item_with_date_due(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test that a date-only due value is widened to a datetime.

    pyicloud reads tzinfo and timestamp() off the value it is given, so a
    plain date would raise AttributeError before reaching iCloud.
    """
    await _setup(hass, config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ITEM: "Eggs",
            ATTR_DUE_DATE: date(2024, 5, 1),
        },
        blocking=True,
    )

    assert reminders.create.call_args.kwargs["due_date"] == datetime(2024, 5, 1)
    assert reminders.create.call_args.kwargs["all_day"] is True


async def test_update_item_with_datetime_due(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test that a timed due value clears the all-day flag."""
    existing = _reminder("r1", "Milk")
    existing.all_day = True
    reminders.get.return_value = existing

    await _setup(hass, config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ITEM: "Milk",
            ATTR_DUE_DATETIME: datetime(2024, 5, 1, 9, 30),
        },
        blocking=True,
    )

    assert existing.all_day is False
    # Home Assistant hands the platform a timezone-aware value.
    assert existing.due_date.tzinfo is not None
    assert existing.due_date.replace(tzinfo=None) == datetime(2024, 5, 1, 9, 30)


async def test_nested_subtasks_follow_their_parent(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test that a grandchild stays with its parent rather than sorting last."""
    reminders.list_reminders.return_value = MagicMock(
        reminders=[
            _reminder("r1", "Grandchild", parent="r2"),
            _reminder("r2", "Child", parent="r3"),
            _reminder("r3", "Parent"),
            _reminder("r4", "Other"),
        ]
    )

    await _setup(hass, config_entry)

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    summaries = [item["summary"] for item in result[ENTITY_ID]["items"]]
    assert summaries == ["Parent", "Child", "Grandchild", "Other"]


async def test_orphaned_subtask_is_kept(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test that a subtask whose parent is absent is still listed.

    The parent may live in another list, so the subtask has no anchor here.
    It must still appear, and must not spin the ordering loop.
    """
    reminders.list_reminders.return_value = MagicMock(
        reminders=[
            _reminder("r1", "Top level"),
            _reminder("r2", "Orphan", parent="missing"),
            _reminder("r3", "Orphan child", parent="r2"),
        ]
    )

    await _setup(hass, config_entry)

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    summaries = [item["summary"] for item in result[ENTITY_ID]["items"]]
    assert summaries == ["Top level", "Orphan", "Orphan child"]


async def test_orphan_parent_returned_after_its_child(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reminders: MagicMock,
) -> None:
    """Test that an orphan still comes before its own child.

    iCloud gives no ordering guarantee, so the child of a subtask whose parent
    is missing can arrive first. The subtask is the root of what is present.
    """
    reminders.list_reminders.return_value = MagicMock(
        reminders=[
            _reminder("r1", "Grandchild", parent="r2"),
            _reminder("r2", "Child", parent="missing"),
        ]
    )

    await _setup(hass, config_entry)

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    summaries = [item["summary"] for item in result[ENTITY_ID]["items"]]
    assert summaries == ["Child", "Grandchild"]


async def test_update_refused_when_title_undecrypted(
    hass: HomeAssistant,
    config_entry: MagicMock,
    reminders: MagicMock,
) -> None:
    """Test that a reminder with an undecryptable title is not written back.

    pyicloud's update() rewrites TitleDocument and NotesDocument
    unconditionally, so persisting the placeholder would destroy the real
    title and blank the notes.
    """
    existing = _reminder("r1", UNDECODED_TITLE)
    reminders.get.return_value = existing

    await _setup(hass, config_entry)

    with pytest.raises(HomeAssistantError, match="could not be decrypted"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_ITEM: "Milk",
                ATTR_STATUS: "completed",
            },
            blocking=True,
        )

    reminders.update.assert_not_called()


async def test_missing_reminder_raises_service_error(
    hass: HomeAssistant,
    config_entry: MagicMock,
    reminders: MagicMock,
) -> None:
    """Test that a reminder deleted elsewhere surfaces as a service error."""
    reminders.get.side_effect = LookupError("Reminder not found: r1")

    await _setup(hass, config_entry)

    with pytest.raises(HomeAssistantError, match="Error updating reminders"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: "Milk"},
            blocking=True,
        )


async def test_undecryptable_reminders_are_left_out(
    hass: HomeAssistant,
    config_entry: MagicMock,
    reminders: MagicMock,
) -> None:
    """Test that reminders which cannot be decrypted are skipped.

    On an Advanced Data Protection account pyicloud returns a placeholder
    title and no notes, which is worse than useless in a to-do list, and
    writing such a reminder back would destroy its real content.
    """
    reminders.list_reminders.return_value = MagicMock(
        reminders=[
            _reminder("r1", "Milk"),
            _reminder("r2", UNDECODED_TITLE),
        ]
    )

    await _setup(hass, config_entry)

    items = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    summaries = [item["summary"] for item in items[ENTITY_ID]["items"]]
    assert summaries == ["Milk"]


async def test_warns_once_when_titles_undecrypted(
    hass: HomeAssistant,
    config_entry: MagicMock,
    reminders: MagicMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that encrypted reminders are explained once, not on every poll."""
    reminders.list_reminders.return_value = MagicMock(
        reminders=[_reminder("r1", UNDECODED_TITLE)]
    )

    await _setup(hass, config_entry)
    assert "could not be decrypted" in caplog.text

    caplog.clear()
    freezer.tick(REMINDERS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # The scheduled refresh runs as a background task of the config entry.
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "could not be decrypted" not in caplog.text


async def test_entry_loads_when_reminders_fail(
    hass: HomeAssistant,
    config_entry: MagicMock,
    reminders: MagicMock,
) -> None:
    """Test that a Reminders outage does not stop the entry loading.

    The coordinator is refreshed before the platforms are forwarded, but
    without raising: the rest of the integration, and the reauth flow for a
    failed login, must keep working regardless of Reminders.
    """
    reminders.lists.side_effect = RemindersApiError("boom")

    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID) is None
