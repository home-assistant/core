"""Conftest for Picnic tests."""

from collections.abc import Awaitable, Callable
import json
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.picnic import CONF_COUNTRY_CODE, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.typing import WebSocketGenerator

ENTITY_ID = "todo.mock_title_shopping_cart"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: "x-original-picnic-auth-token",
            CONF_COUNTRY_CODE: "NL",
        },
        unique_id="295-6y3-1nf4",
    )


@pytest.fixture
def mock_picnic_api():
    """Return a mocked PicnicAPI client."""
    with patch("homeassistant.components.picnic.PicnicAPI") as mock:
        client = mock.return_value
        client.session.auth_token = "3q29fpwhulzes"
        client.get_cart.return_value = json.loads(load_fixture("picnic/cart.json"))
        client.get_user.return_value = json.loads(load_fixture("picnic/user.json"))
        client.get_deliveries.return_value = json.loads(
            load_fixture("picnic/delivery.json")
        )
        client.get_delivery_position.return_value = {}
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_picnic_api: MagicMock
) -> MockConfigEntry:
    """Set up the Picnic integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
async def get_items(
    hass_ws_client: WebSocketGenerator,
) -> Callable[[], Awaitable[dict[str, str]]]:
    """Fixture to fetch items from the todo websocket."""

    async def get() -> list[dict[str, str]]:
        # Fetch items using To-do platform
        client = await hass_ws_client()
        await client.send_json_auto_id(
            {
                "id": id,
                "type": "todo/item/list",
                "entity_id": ENTITY_ID,
            }
        )
        resp = await client.receive_json()
        assert resp.get("success")
        return resp.get("result", {}).get("items", [])

    return get
