"""Test the trello config flow."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from trello import Unauthorized

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.trello.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import BOARD_LISTS

from tests.common import MockConfigEntry

API_KEY = "an_api_key"
API_TOKEN = "an_api_token"
USER_ID = "a_user_id"
EMAIL_ADDR = "an_email"

BOARD_ID = "a_board_id"

BOARD_ID_LISTS = {
    BOARD_ID: BOARD_LISTS,
}

USER_INPUT_CREDS = {"api_key": API_KEY, "api_token": API_TOKEN}


class MockAdapter:
    """Mock TrelloAdapter."""

    def __init__(self, trello_client) -> None:
        """Init mock TrelloAdapter."""

    def get_member(self):
        """Mock member object."""
        return SimpleNamespace(id=USER_ID, email=EMAIL_ADDR)

    def get_boards(self):
        """Mock board dict."""
        return {BOARD_ID: {"id": BOARD_ID, "name": "a_board_name"}}

    def get_board_lists(self, id_boards, selected_board_ids):
        """Mock board dict."""
        return BOARD_ID_LISTS


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test full user setup flow."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.trello.config_flow.TrelloAdapter",
        new=MockAdapter,
    ), patch(
        "homeassistant.components.trello.async_setup_entry",
        return_value=True,
    ):
        creds_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"], user_input=USER_INPUT_CREDS
        )

        board_selection_result = await hass.config_entries.flow.async_configure(
            creds_result["flow_id"],
            user_input={"board_ids": [BOARD_ID]},
        )

    assert init_result["type"] == FlowResultType.FORM
    assert init_result["step_id"] == "user"
    assert init_result["last_step"] is False

    assert creds_result["step_id"] == "finish"
    assert creds_result["last_step"] is True
    assert creds_result["data_schema"].schema["board_ids"].options == {
        BOARD_ID: "a_board_name"
    }

    assert board_selection_result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert board_selection_result["data"] == {
        "api_key": API_KEY,
        "api_token": API_TOKEN,
        "user_id": USER_ID,
        "user_email": EMAIL_ADDR,
    }
    assert board_selection_result["options"] == {"boards": BOARD_ID_LISTS}
    assert board_selection_result["result"].unique_id == USER_ID
    assert board_selection_result["result"].title == EMAIL_ADDR


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test full options configuration flow."""
    entry = MockConfigEntry(
        domain="trello",
        data=USER_INPUT_CREDS,
        options={"boards": BOARD_ID_LISTS},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trello.config_flow.TrelloAdapter",
        new=MockAdapter,
    ), patch("homeassistant.components.trello.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
        init_result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        await hass.config_entries.options.async_configure(
            init_result["flow_id"],
            user_input={"board_ids": [BOARD_ID]},
        )
        await hass.async_block_till_done()

    assert init_result["type"] == FlowResultType.FORM
    assert init_result["step_id"] == "init"
    assert init_result["data_schema"].schema["board_ids"].options == {
        BOARD_ID: "a_board_name"
    }
    assert list(init_result["data_schema"].schema.keys())[0].default() == [BOARD_ID]


async def test_options_flow_remove_board(hass: HomeAssistant) -> None:
    """Test options flow when user deselects a previously selected board."""
    entry = MockConfigEntry(
        domain="trello",
        data=USER_INPUT_CREDS,
        options={"boards": BOARD_ID_LISTS},
        unique_id="a_unique_id",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trello.config_flow.TrelloAdapter",
        new=MockAdapter,
    ), patch(
        "homeassistant.components.trello.sensor.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.trello.config_flow.dr"
    ) as device_registry:
        await hass.config_entries.async_setup(entry.entry_id)
        init_result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        dev_reg = Mock()
        device_registry.async_get.return_value = dev_reg

        await hass.config_entries.options.async_configure(
            init_result["flow_id"],
            user_input={"board_ids": []},
        )
        await hass.async_block_till_done()

        dev_reg.async_remove_device.assert_called_once()


async def test_flow_user_unauthorized(hass: HomeAssistant) -> None:
    """Test user setup flow when user enters invalid creds."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.trello.config_flow.TrelloAdapter.get_member",
        side_effect=Unauthorized("", Mock(status=123)),
    ), patch(
        "homeassistant.components.trello.async_setup_entry",
        return_value=True,
    ):
        creds_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input=USER_INPUT_CREDS,
        )

    assert creds_result["type"] == FlowResultType.FORM
    assert creds_result["step_id"] == "user"
    assert creds_result["errors"] == {"base": "invalid_auth"}
    assert creds_result["last_step"] is False
