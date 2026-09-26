"""Common fixtures for AnyList tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioanylist import AuthTokens
from aioanylist.proto import PB
from aioanylist.state import AnyListState
import pytest

from homeassistant.components.anylist.const import (
    CONF_REFRESH_TOKEN,
    CONF_USER_LOCALE,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_EMAIL

from tests.common import MockConfigEntry

EMAIL = "person@example.com"
USER_ID = "user-123"
CLIENT_ID = "0123456789abcdef0123456789abcdef"
ACCESS_TOKEN = "access-token"
REFRESH_TOKEN = "refresh-token"
USER_LOCALE = "en-US"

LIST_ID = "list-1"
ITEM_ID = "item-1"
COMPLETED_ITEM_ID = "item-2"


def build_state() -> AnyListState:
    """Build representative AnyList state."""
    state = AnyListState(user_id=USER_ID)
    shopping_list = PB.ShoppingList(identifier=LIST_ID, name="Groceries")
    shopping_list.items.add(
        identifier=ITEM_ID,
        listId=LIST_ID,
        name="Milk",
        details="2%",
        checked=False,
    )
    shopping_list.items.add(
        identifier=COMPLETED_ITEM_ID,
        listId=LIST_ID,
        name="Bread",
        checked=True,
    )
    state.shopping_lists[LIST_ID] = shopping_list
    state.ordered_shopping_list_ids.append(LIST_ID)
    state.loaded_once = True
    return state


@pytest.fixture(name="mock_config_entry")
def mock_config_entry_fixture() -> MockConfigEntry:
    """Return a configured AnyList entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        unique_id=USER_ID,
        data={
            CONF_EMAIL: EMAIL,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_REFRESH_TOKEN: REFRESH_TOKEN,
            CONF_USER_LOCALE: USER_LOCALE,
        },
    )


@pytest.fixture(name="mock_anylist_client")
def mock_anylist_client_fixture() -> Generator[MagicMock]:
    """Mock the aioanylist client used by config flow and runtime setup."""
    client = MagicMock()
    client.state = build_state()
    client.sign_in = AsyncMock(
        return_value=AuthTokens(
            user_id=USER_ID,
            access_token=ACCESS_TOKEN,
            refresh_token=REFRESH_TOKEN,
            user_locale=USER_LOCALE,
        )
    )
    client.load = AsyncMock(return_value=client.state)
    client.refresh = AsyncMock(return_value=client.state)
    client.flush = AsyncMock()
    client.close = AsyncMock()

    client.sync = MagicMock()
    client.sync_listener = None
    client.sync_status_listener = None

    def add_sync_listener(listener) -> None:
        client.sync_listener = listener

    def add_sync_status_listener(listener) -> None:
        client.sync_status_listener = listener

    client.sync.add_listener.side_effect = add_sync_listener
    client.sync.add_status_listener.side_effect = add_sync_status_listener

    lists = MagicMock()
    lists.item.side_effect = client.state.get_item
    lists.add_item = AsyncMock()
    lists.rename_item = AsyncMock()
    lists.set_checked = AsyncMock()
    lists.set_details = AsyncMock()
    lists.bulk_remove_items = AsyncMock()
    client.lists = lists

    def create_client(*args, **kwargs):
        client.token_callback = kwargs.get("token_callback")
        return client

    with (
        patch(
            "homeassistant.components.anylist.AnyListClient", side_effect=create_client
        ),
        patch(
            "homeassistant.components.anylist.config_flow.AnyListClient",
            side_effect=create_client,
        ),
    ):
        yield client
