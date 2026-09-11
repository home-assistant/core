"""Test the Remember The Milk integration."""

from collections.abc import Callable
from datetime import timedelta
from types import MappingProxyType
from unittest.mock import MagicMock, patch

from aiortm import AioRTMError, AuthError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.remember_the_milk.const import (
    CONF_LIST_ID,
    DOMAIN,
    SUBENTRY_TYPE_LIST,
)
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryDataWithId,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import CREATE_ENTRY_DATA, PROFILE

from tests.common import MockConfigEntry, async_fire_time_changed

LIST_ID = 42
NEW_LIST_ID = 100
SUBENTRY_ID = "test-subentry-id"

CONFIG = {
    "name": "myprofile",
    "api_key": "test-api-key",
    "shared_secret": "test-shared-secret",
}


@pytest.fixture
def config_entry_with_subentry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry with one list subentry."""
    entry = MockConfigEntry(
        data=CREATE_ENTRY_DATA,
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_LIST_ID: LIST_ID},
                subentry_type=SUBENTRY_TYPE_LIST,
                title="Shopping",
                unique_id=str(LIST_ID),
                subentry_id=SUBENTRY_ID,
            )
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.usefixtures("client", "storage")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading a config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("storage")
@pytest.mark.parametrize(
    ("side_effect", "entry_state", "ignore_missing_translations"),
    [
        pytest.param(
            AuthError("Invalid token!"),
            ConfigEntryState.SETUP_ERROR,
            [
                f"component.{DOMAIN}.services.{PROFILE}_create_task.",
                f"component.{DOMAIN}.services.{PROFILE}_complete_task.",
            ],
            id="auth_error",
        ),
        pytest.param(
            AioRTMError("Connection failed!"),
            ConfigEntryState.SETUP_RETRY,
            [],
            id="rtm_error",
        ),
    ],
)
async def test_config_entry_check_token_fails(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test that token check failures put the entry in the expected state."""
    client.rtm.api.check_token.side_effect = side_effect

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is entry_state


@pytest.mark.usefixtures("client", "storage")
async def test_import_creates_deprecation_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a successful YAML import creates a deprecation repair issue."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: CONFIG})
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            AuthError("Invalid token!"),
            ConfigEntryState.SETUP_ERROR,
            id="auth_error",
        ),
        pytest.param(
            AioRTMError("Boom!"),
            ConfigEntryState.SETUP_RETRY,
            id="api_error",
        ),
    ],
)
@pytest.mark.usefixtures("storage")
async def test_coordinator_update_errors(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test config entry state when the first coordinator refresh fails."""
    client.rtm.tasks.get_list.side_effect = side_effect
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is expected_state


@pytest.mark.parametrize("ignore_missing_translations", [[]])
@pytest.mark.usefixtures("client")
async def test_import_without_token_creates_issue(
    hass: HomeAssistant,
    storage: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import without a stored token aborts and creates an issue.

    Without a token the import can't be completed, so no config entry is
    created and the user is guided to set the integration up via the UI.
    """
    storage.get_token.return_value = None

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: CONFIG})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_auth"
    )


@pytest.mark.usefixtures("storage")
async def test_remove_subentry_deletes_list(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry_with_subentry: MockConfigEntry,
    rtm_list_mock: Callable[[int, str], MagicMock],
) -> None:
    """Test that removing a list sub-entry deletes the list on the RTM server."""
    rtm_list_mock(LIST_ID, "Shopping")

    await hass.config_entries.async_setup(config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()
    assert config_entry_with_subentry.state is ConfigEntryState.LOADED

    hass.config_entries.async_remove_subentry(config_entry_with_subentry, SUBENTRY_ID)
    await hass.async_block_till_done()

    client.rtm.timelines.create.assert_called_once()
    client.rtm.lists.delete.assert_called_once_with(
        timeline=client.rtm.timelines.create.return_value.timeline,
        list_id=LIST_ID,
    )


@pytest.mark.usefixtures("storage")
async def test_rename_subentry_does_not_delete_list(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry_with_subentry: MockConfigEntry,
    rtm_list_mock: Callable[[int, str], MagicMock],
) -> None:
    """Test that renaming a sub-entry (no list removed) does not trigger deletion."""
    rtm_list_mock(LIST_ID, "Shopping")

    await hass.config_entries.async_setup(config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()
    assert config_entry_with_subentry.state is ConfigEntryState.LOADED

    subentry = next(iter(config_entry_with_subentry.subentries.values()))
    hass.config_entries.async_update_subentry(
        config_entry_with_subentry, subentry, title="Grocery Shopping"
    )
    await hass.async_block_till_done()

    client.rtm.lists.delete.assert_not_called()


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(AuthError("Invalid token!"), id="auth_error"),
        pytest.param(AioRTMError("Boom!"), id="api_error"),
    ],
)
@pytest.mark.usefixtures("storage")
async def test_remove_subentry_delete_list_error(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry_with_subentry: MockConfigEntry,
    side_effect: Exception,
    rtm_list_mock: Callable[[int, str], MagicMock],
) -> None:
    """Test that a server error when deleting a list is logged and reload still runs."""
    rtm_list_mock(LIST_ID, "Shopping")

    await hass.config_entries.async_setup(config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()
    assert config_entry_with_subentry.state is ConfigEntryState.LOADED

    client.rtm.lists.delete.side_effect = side_effect

    hass.config_entries.async_remove_subentry(config_entry_with_subentry, SUBENTRY_ID)
    await hass.async_block_till_done()

    client.rtm.lists.delete.assert_called_once()
    assert config_entry_with_subentry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("storage")
async def test_coordinator_creates_subentry_for_new_list(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    rtm_list_mock: Callable[[int, str], MagicMock],
) -> None:
    """Test that a list on the server creates a subentry and todo entity during first refresh."""
    rtm_list_mock(LIST_ID, "Shopping")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert len(config_entry.subentries) == 1
    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.data[CONF_LIST_ID] == LIST_ID
    assert subentry.title == "Shopping"
    assert subentry.unique_id == str(LIST_ID)
    assert hass.states.get("todo.shopping") is not None
    client.rtm.lists.delete.assert_not_called()


@pytest.mark.usefixtures("storage")
async def test_coordinator_removes_subentry_when_list_gone(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry_with_subentry: MockConfigEntry,
) -> None:
    """Test that a list gone from the server removes the subentry without a server delete."""
    # rtm.lists.get_list returns empty by default — list 42 has disappeared from the server.
    await hass.config_entries.async_setup(config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_subentry.state is ConfigEntryState.LOADED
    assert len(config_entry_with_subentry.subentries) == 0
    client.rtm.lists.delete.assert_not_called()


@pytest.mark.usefixtures("client", "storage")
async def test_coordinator_updates_subentry_title_on_rename(
    hass: HomeAssistant,
    config_entry_with_subentry: MockConfigEntry,
    rtm_list_mock: Callable[[int, str], MagicMock],
) -> None:
    """Test that a server-side list rename updates the subentry title."""
    rtm_list_mock(
        LIST_ID, "Grocery Shopping"
    )  # Different from the subentry title "Shopping"

    await hass.config_entries.async_setup(config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_subentry.state is ConfigEntryState.LOADED
    subentry = config_entry_with_subentry.subentries.get(SUBENTRY_ID)
    assert subentry is not None
    assert subentry.title == "Grocery Shopping"


@pytest.mark.usefixtures("storage")
async def test_coordinator_ignores_filtered_lists(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    make_rtm_list_mock: Callable[..., MagicMock],
) -> None:
    """Test that smart, archived, locked, and deleted lists are not synced as subentries."""
    lists_response = MagicMock()
    lists_response.lists = [
        make_rtm_list_mock(1, "Normal"),
        make_rtm_list_mock(2, "Smart", smart=True),
        make_rtm_list_mock(3, "Archived", archived=True),
        make_rtm_list_mock(4, "Locked", locked=True),
        make_rtm_list_mock(5, "Deleted", deleted=True),
    ]
    client.rtm.lists.get_list.return_value = lists_response

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert len(config_entry.subentries) == 1
    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.title == "Normal"
    assert subentry.data[CONF_LIST_ID] == 1


@pytest.mark.usefixtures("storage")
async def test_coordinator_skips_tasks_for_filtered_list(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    rtm_list_mock: Callable[[int, str], MagicMock],
) -> None:
    """Test that tasks for a list absent from the lists result (e.g. filtered) are ignored."""
    rtm_list_mock(LIST_ID, "Shopping")
    # A task_list whose id is not in the coordinator result (simulates a filtered list).
    task_list = MagicMock()
    task_list.id = 999
    tasks_response = MagicMock()
    tasks_response.tasks.task_list = [task_list]
    client.rtm.tasks.get_list.return_value = tasks_response

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert len(config_entry.subentries) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "ignore_missing_translations"),
    [
        pytest.param(
            AuthError("Invalid token!"),
            ConfigEntryState.SETUP_ERROR,
            [
                f"component.{DOMAIN}.services.{PROFILE}_create_task.",
                f"component.{DOMAIN}.services.{PROFILE}_complete_task.",
            ],
            id="auth_error",
        ),
        pytest.param(
            AioRTMError("Boom!"),
            ConfigEntryState.SETUP_RETRY,
            [
                f"component.{DOMAIN}.services.{PROFILE}_create_task.",
                f"component.{DOMAIN}.services.{PROFILE}_complete_task.",
            ],
            id="api_error",
        ),
    ],
)
@pytest.mark.usefixtures("storage")
async def test_coordinator_lists_fetch_errors(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test config entry state when the list fetch in the coordinator fails."""
    client.rtm.lists.get_list.side_effect = side_effect
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is expected_state


@pytest.mark.usefixtures("storage")
async def test_coordinator_does_not_delete_server_removed_list(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    rtm_list_mock: Callable[[int, str], MagicMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a list removed from the server on a subsequent poll is not deleted.

    The update listener computes lists to delete by comparing the current subentries
    against the coordinator's last-known server data. If it runs before coordinator.data
    is updated with the fresh (shorter) list, a server-side removal looks like a
    user-initiated deletion and the list would be permanently deleted on the server.
    """
    rtm_list_mock(LIST_ID, "Shopping")
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert len(config_entry.subentries) == 1

    # List disappears from the server (e.g. archived) on the next poll.
    lists_response = MagicMock()
    lists_response.lists = []
    client.rtm.lists.get_list.return_value = lists_response

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(config_entry.subentries) == 0
    client.rtm.lists.delete.assert_not_called()


@pytest.mark.usefixtures("storage")
async def test_coordinator_sync_multiple_new_lists_no_deletion(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    make_rtm_list_mock: Callable[..., MagicMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that discovering multiple new lists in one poll doesn't delete any of them.

    Each async_add_subentry call fires the update listener eagerly. Without the
    syncing_subentries guard, the listener would see an incomplete subentry set
    mid-sync and wrongly delete the not-yet-added list from the server.
    """
    lists_response = MagicMock()
    lists_response.lists = [make_rtm_list_mock(LIST_ID, "Shopping")]
    client.rtm.lists.get_list.return_value = lists_response

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert len(config_entry.subentries) == 1

    # Two new lists appear simultaneously on the server on the next poll.
    lists_response = MagicMock()
    lists_response.lists = [
        make_rtm_list_mock(LIST_ID, "Shopping"),
        make_rtm_list_mock(LIST_ID + 1, "Work"),
        make_rtm_list_mock(LIST_ID + 2, "Personal"),
    ]
    client.rtm.lists.get_list.return_value = lists_response

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(config_entry.subentries) == 3
    client.rtm.lists.delete.assert_not_called()


@pytest.mark.usefixtures("storage")
async def test_coordinator_sync_multiple_lists_single_reload(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    make_rtm_list_mock: Callable[..., MagicMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that discovering multiple new lists in one poll schedules a single reload."""
    # Empty list response during setup so no subentries are added and no reload fires.
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert len(config_entry.subentries) == 0

    # Three new lists appear simultaneously on the next poll.
    lists_response = MagicMock()
    lists_response.lists = [
        make_rtm_list_mock(LIST_ID, "Shopping"),
        make_rtm_list_mock(LIST_ID + 1, "Work"),
        make_rtm_list_mock(LIST_ID + 2, "Personal"),
    ]
    client.rtm.lists.get_list.return_value = lists_response

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        freezer.tick(timedelta(minutes=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_reload.assert_called_once_with(config_entry.entry_id)


@pytest.mark.usefixtures("storage")
async def test_coordinator_sync_no_changes_no_reload(
    hass: HomeAssistant,
    config_entry_with_subentry: MockConfigEntry,
    rtm_list_mock: Callable[[int, str], MagicMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a coordinator poll with unchanged subentries schedules no reload."""
    rtm_list_mock(LIST_ID, "Shopping")

    await hass.config_entries.async_setup(config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()
    assert config_entry_with_subentry.state is ConfigEntryState.LOADED
    assert len(config_entry_with_subentry.subentries) == 1

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        freezer.tick(timedelta(minutes=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_reload.assert_not_called()


@pytest.mark.usefixtures("client", "storage")
async def test_coordinator_polls_when_no_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    rtm_list_mock: Callable[[int, str], MagicMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the coordinator keeps polling even when there are no todo entities.

    When there are no eligible RTM lists there are no subentries and therefore no
    CoordinatorEntity listeners. Without a permanent listener the coordinator stops
    scheduling refreshes after the first one, so lists created later in RTM are
    never discovered.
    """
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert len(config_entry.subentries) == 0

    # A new list appears on the server.
    rtm_list_mock(LIST_ID, "Shopping")

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(config_entry.subentries) == 1
    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.data[CONF_LIST_ID] == LIST_ID


@pytest.mark.usefixtures("client", "storage")
async def test_update_listener_registered_before_forward(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test that a subentry added during platform forwarding triggers a reload.

    The update listener must be registered before async_forward_entry_setups so
    that a subentry appearing in the reconciliation window (after todo.async_setup_entry
    enumerated subentries but before the listener is installed) still fires a reload and
    gets picked up.
    """
    original_forward = hass.config_entries.async_forward_entry_setups

    async def forward_and_add(entry, platforms):
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType({CONF_LIST_ID: NEW_LIST_ID}),
                subentry_type=SUBENTRY_TYPE_LIST,
                title="Late List",
                unique_id=str(NEW_LIST_ID),
            ),
        )
        await original_forward(entry, platforms)

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            side_effect=forward_and_add,
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    mock_reload.assert_called_with(config_entry.entry_id)
