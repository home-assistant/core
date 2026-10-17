"""Test the Remember The Milk todo platform."""

from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import MagicMock

from aiortm import AioRTMError, AuthError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.remember_the_milk.const import (
    CONF_LIST_ID,
    DOMAIN,
    SUBENTRY_TYPE_LIST,
)
from homeassistant.components.todo import (
    ATTR_DESCRIPTION,
    ATTR_DUE_DATE,
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoItemStatus,
    TodoServices,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import CREATE_ENTRY_DATA

from tests.common import MockConfigEntry

SUBENTRY_ID = "test-subentry-id"
LIST_ID = 99
ENTITY_ID = "todo.my_shopping_list"


def _make_task_list(
    list_id: int,
    taskseries_id: int,
    task_id: int,
    name: str,
    completed: datetime | None = None,
    deleted: datetime | None = None,
    due: datetime | None = None,
    has_due_time: bool = False,
    notes: list | None = None,
) -> MagicMock:
    """Build a minimal mock RTM task list response for one task."""
    task_list = MagicMock()
    task_list.id = list_id
    taskseries = MagicMock()
    taskseries.id = taskseries_id
    taskseries.name = name
    taskseries.notes = notes or []
    task = MagicMock()
    task.id = task_id
    task.completed = completed
    task.deleted = deleted
    task.due = due
    task.has_due_time = has_due_time
    taskseries.task = [task]
    task_list.taskseries = [taskseries]
    return task_list


def _set_tasks_response(client: MagicMock, *task_lists: MagicMock) -> None:
    """Configure the client to return the given task lists from tasks.get_list."""
    tasks_response = MagicMock()
    tasks_response.tasks.task_list = list(task_lists)
    client.rtm.tasks.get_list.return_value = tasks_response


@pytest.fixture(autouse=True)
def _lists_response(rtm_list_mock: Callable[[int, str], MagicMock]) -> None:
    """Return list 99 for all todo tests so the list subentry is kept during coordinator sync."""
    rtm_list_mock(LIST_ID, "My Shopping List")


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry with one list subentry."""
    entry = MockConfigEntry(
        data=CREATE_ENTRY_DATA,
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_LIST_ID: LIST_ID},
                subentry_type=SUBENTRY_TYPE_LIST,
                title="My Shopping List",
                unique_id=str(LIST_ID),
                subentry_id=SUBENTRY_ID,
            )
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.usefixtures("storage")
async def test_entity_state(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the entity state reflects incomplete task count."""
    _set_tasks_response(
        client,
        _make_task_list(LIST_ID, 10, 1, "Buy milk"),
        _make_task_list(
            LIST_ID, 20, 2, "Eggs", completed=datetime(2024, 1, 1, tzinfo=UTC)
        ),
        _make_task_list(
            LIST_ID, 30, 3, "Bread", deleted=datetime(2024, 1, 1, tzinfo=UTC)
        ),
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    # 1 active ("Buy milk"), 1 completed ("Eggs"), 1 deleted ("Bread" — excluded)
    assert state.state == "1"


@pytest.mark.usefixtures("client", "storage")
async def test_device_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a device entry is created for the todo list entity."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, SUBENTRY_ID), config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.usefixtures("storage")
async def test_create_todo_item(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test creating a todo item calls the RTM tasks.add API."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: "Buy butter"},
        blocking=True,
    )

    client.rtm.tasks.add.assert_called_once_with(
        timeline=1234,
        name="Buy butter",
        list_id=LIST_ID,
        parse=True,
    )
    client.rtm.tasks.get_list.assert_called()


@pytest.mark.usefixtures("storage")
async def test_create_todo_item_with_due_date(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test creating a todo item with a due date."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ITEM: "Buy butter",
            ATTR_DUE_DATE: "2024-03-15",
        },
        blocking=True,
    )

    client.rtm.tasks.add.assert_called_once()
    client.rtm.tasks.set_due_date.assert_called_once_with(
        timeline=1234,
        list_id=1,  # from mock response task_list.id
        taskseries_id=2,  # from mock response taskseries.id
        task_id=3,  # from mock response task.id
        due="2024-03-15",
        has_due_time=False,
    )


@pytest.mark.usefixtures("storage")
async def test_create_todo_item_with_description(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test creating a todo item with a description adds a note."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ITEM: "Buy butter",
            ATTR_DESCRIPTION: "Full fat please",
        },
        blocking=True,
    )

    client.rtm.tasks.add.assert_called_once()
    client.rtm.tasks.notes.add.assert_called_once_with(
        timeline=1234,
        list_id=1,
        taskseries_id=2,
        task_id=3,
        title="",
        text="Full fat please",
    )


@pytest.mark.parametrize(
    "new_name",
    [
        pytest.param("Buy whole milk", id="different_name"),
        pytest.param("Buy milk", id="same_name"),
    ],
)
@pytest.mark.usefixtures("storage")
async def test_update_todo_item_rename(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    new_name: str,
) -> None:
    """Test renaming a todo item always calls tasks.set_name, even when the name is unchanged."""
    _set_tasks_response(client, _make_task_list(LIST_ID, 10, 1, "Buy milk"))

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    uid = f"{LIST_ID}_10_1"
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: uid, ATTR_RENAME: new_name},
        blocking=True,
    )

    client.rtm.tasks.set_name.assert_called_once_with(
        timeline=1234,
        list_id=LIST_ID,
        taskseries_id=10,
        task_id=1,
        name=new_name,
    )


@pytest.mark.parametrize(
    ("initial_completed", "target_status", "expected_api", "not_expected_api"),
    [
        pytest.param(
            None,
            TodoItemStatus.COMPLETED,
            "complete",
            "uncomplete",  # codespell:ignore uncomplete
            id="incomplete_to_complete",
        ),
        pytest.param(
            datetime(2024, 1, 1, tzinfo=UTC),
            TodoItemStatus.NEEDS_ACTION,
            "uncomplete",  # codespell:ignore uncomplete
            "complete",
            id="complete_to_incomplete",
        ),
        pytest.param(
            datetime(2024, 1, 1, tzinfo=UTC),
            TodoItemStatus.COMPLETED,
            "complete",
            "uncomplete",  # codespell:ignore uncomplete
            id="already_complete",
        ),
        pytest.param(
            None,
            TodoItemStatus.NEEDS_ACTION,
            "uncomplete",  # codespell:ignore uncomplete
            "complete",
            id="already_incomplete",
        ),
    ],
)
@pytest.mark.usefixtures("storage")
async def test_update_todo_item_status(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    initial_completed: datetime | None,
    target_status: TodoItemStatus,
    expected_api: str,
    not_expected_api: str,
) -> None:
    """Test updating item status always calls the correct RTM API, even when unchanged."""
    _set_tasks_response(
        client, _make_task_list(LIST_ID, 10, 1, "Buy milk", completed=initial_completed)
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    uid = f"{LIST_ID}_10_1"
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: uid, ATTR_STATUS: target_status},
        blocking=True,
    )

    getattr(client.rtm.tasks, expected_api).assert_called_once_with(
        timeline=1234,
        list_id=LIST_ID,
        taskseries_id=10,
        task_id=1,
    )
    getattr(client.rtm.tasks, not_expected_api).assert_not_called()


@pytest.mark.usefixtures("storage")
async def test_delete_todo_items(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test deleting todo items calls tasks.delete for each uid."""
    _set_tasks_response(
        client,
        _make_task_list(LIST_ID, 10, 1, "Buy milk"),
        _make_task_list(LIST_ID, 20, 2, "Buy eggs"),
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    uid1 = f"{LIST_ID}_10_1"
    uid2 = f"{LIST_ID}_20_2"
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: [uid1, uid2]},
        blocking=True,
    )

    assert client.rtm.tasks.delete.call_count == 2
    client.rtm.tasks.delete.assert_any_call(
        timeline=1234, list_id=LIST_ID, taskseries_id=10, task_id=1
    )
    client.rtm.tasks.delete.assert_any_call(
        timeline=1234, list_id=LIST_ID, taskseries_id=20, task_id=2
    )


@pytest.mark.parametrize(
    ("initial_due", "new_due_str", "expected_due", "expected_has_due_time"),
    [
        pytest.param(None, "2024-03-15", "2024-03-15", False, id="no_due_to_due"),
        pytest.param(
            datetime(2024, 3, 15, tzinfo=UTC),
            "2024-03-15",
            "2024-03-15",
            False,
            id="same_due",
        ),
    ],
)
@pytest.mark.usefixtures("storage")
async def test_update_todo_item_set_due_date(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    initial_due: datetime | None,
    new_due_str: str,
    expected_due: str,
    expected_has_due_time: bool,
) -> None:
    """Test updating due date always calls tasks.set_due_date, even when unchanged."""
    _set_tasks_response(
        client, _make_task_list(LIST_ID, 10, 1, "Buy milk", due=initial_due)
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    uid = f"{LIST_ID}_10_1"
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: uid, ATTR_DUE_DATE: new_due_str},
        blocking=True,
    )

    client.rtm.tasks.set_due_date.assert_called_once_with(
        timeline=1234,
        list_id=LIST_ID,
        taskseries_id=10,
        task_id=1,
        due=expected_due,
        has_due_time=expected_has_due_time,
    )


@pytest.mark.usefixtures("storage")
async def test_update_todo_item_add_description(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test updating a todo item to add a description adds a note."""
    _set_tasks_response(client, _make_task_list(LIST_ID, 10, 1, "Buy milk"))

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    uid = f"{LIST_ID}_10_1"
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ITEM: uid,
            ATTR_DESCRIPTION: "Organic if possible",
        },
        blocking=True,
    )

    client.rtm.tasks.notes.add.assert_called_once_with(
        timeline=1234,
        list_id=LIST_ID,
        taskseries_id=10,
        task_id=1,
        title="",
        text="Organic if possible",
    )
    client.rtm.tasks.notes.edit.assert_not_called()
    client.rtm.tasks.notes.delete.assert_not_called()


@pytest.mark.parametrize(
    "new_description",
    [
        pytest.param("New description", id="different_description"),
        pytest.param("Old description", id="same_description"),
    ],
)
@pytest.mark.usefixtures("storage")
async def test_update_todo_item_edit_description(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    new_description: str,
) -> None:
    """Test updating a todo item description always edits the note, even when unchanged."""
    note = MagicMock()
    note.id = 55
    note.body = "Old description"
    _set_tasks_response(
        client, _make_task_list(LIST_ID, 10, 1, "Buy milk", notes=[note])
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    uid = f"{LIST_ID}_10_1"
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: uid, ATTR_DESCRIPTION: new_description},
        blocking=True,
    )

    client.rtm.tasks.notes.edit.assert_called_once_with(
        timeline=1234,
        note_id=55,
        title="",
        text=new_description,
    )
    client.rtm.tasks.notes.add.assert_not_called()


@pytest.mark.usefixtures("storage")
async def test_update_todo_item_delete_description(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test clearing a todo item description deletes the note."""
    note = MagicMock()
    note.id = 55
    note.body = "Existing description"
    _set_tasks_response(
        client, _make_task_list(LIST_ID, 10, 1, "Buy milk", notes=[note])
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    uid = f"{LIST_ID}_10_1"
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: uid, ATTR_DESCRIPTION: ""},
        blocking=True,
    )

    client.rtm.tasks.notes.delete.assert_called_once_with(
        timeline=1234,
        note_id=55,
    )
    client.rtm.tasks.notes.add.assert_not_called()
    client.rtm.tasks.notes.edit.assert_not_called()


@pytest.mark.usefixtures("storage")
async def test_update_todo_item_empty_note_preserved(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test that an unrelated update does not delete a note with an empty body.

    RTM notes can have a title but an empty body. The coordinator represents those
    as description=None (because body or None collapses an empty string), but the
    note still has a note_id. An unrelated update (e.g. completing the task) must
    not delete that note.
    """
    note = MagicMock()
    note.id = 55
    note.body = ""
    _set_tasks_response(
        client, _make_task_list(LIST_ID, 10, 1, "Buy milk", notes=[note])
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    uid = f"{LIST_ID}_10_1"
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ITEM: uid,
            ATTR_STATUS: TodoItemStatus.COMPLETED,
        },
        blocking=True,
    )

    client.rtm.tasks.notes.delete.assert_not_called()
    client.rtm.tasks.notes.edit.assert_not_called()
    client.rtm.tasks.notes.add.assert_not_called()


@pytest.mark.usefixtures("client", "storage")
async def test_setup_skips_non_list_subentries(hass: HomeAssistant) -> None:
    """Test that async_setup_entry ignores subentries that are not list subentries."""
    entry = MockConfigEntry(
        data=CREATE_ENTRY_DATA,
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_LIST_ID: LIST_ID},
                subentry_type=SUBENTRY_TYPE_LIST,
                title="My Shopping List",
                unique_id=str(LIST_ID),
                subentry_id=SUBENTRY_ID,
            ),
            ConfigSubentryDataWithId(
                data={},
                subentry_type="other",
                title="Other Subentry",
                unique_id=None,
                subentry_id="extra-subentry-id",
            ),
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Only the list subentry should produce a todo entity.
    assert hass.states.get(ENTITY_ID) is not None
    assert hass.states.get("todo.other_subentry") is None


@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        pytest.param(AuthError("Boom!"), "invalid_auth", id="auth_error"),
        pytest.param(AioRTMError("Boom!"), "api_error", id="api_error"),
    ],
)
@pytest.mark.usefixtures("storage")
async def test_todo_item_api_errors(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    translation_key: str,
) -> None:
    """Test that RTM API errors during a todo operation raise HomeAssistantError."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    client.rtm.timelines.create.side_effect = side_effect
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_ITEM: "Buy butter"},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key
