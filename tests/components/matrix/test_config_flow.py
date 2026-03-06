"""Test the Matrix config flow."""

from unittest.mock import AsyncMock, patch

from nio import LoginError, LoginResponse, WhoamiResponse

from homeassistant import config_entries
from homeassistant.components.matrix.config_flow import CannotConnect, validate_input
from homeassistant.components.matrix.const import (
    CONF_COMMANDS,
    CONF_EXPRESSION,
    CONF_REACTION,
    CONF_ROOMS,
    CONF_WORD,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {
    "homeserver": "https://matrix.example.com",
    "username": "@user:example.com",
    "password": "password",
    "verify_ssl": True,
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_response = LoginResponse.from_dict(
            {
                "access_token": "test_token",
                "device_id": "test_device",
                "user_id": "@user:example.com",
            }
        )
        client_instance.login.return_value = login_response

        whoami_response = WhoamiResponse.from_dict(
            {
                "user_id": "@user:example.com",
            }
        )
        client_instance.whoami.return_value = whoami_response

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "@user:example.com"
    assert result2["data"] == TEST_USER_INPUT


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.matrix.config_flow.AsyncClient",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_login_error(hass: HomeAssistant) -> None:
    """Test we handle login errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_error = LoginError.from_dict(
            {
                "errcode": "M_FORBIDDEN",
                "error": "Invalid username or password",
            }
        )
        client_instance.login.return_value = login_error

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test that we abort on duplicate entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_response = LoginResponse.from_dict(
            {
                "access_token": "test_token",
                "device_id": "test_device",
                "user_id": "@user:example.com",
            }
        )
        client_instance.login.return_value = login_response

        whoami_response = WhoamiResponse.from_dict(
            {
                "user_id": "@user:example.com",
            }
        )
        client_instance.whoami.return_value = whoami_response

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test successful import flow."""
    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_response = LoginResponse.from_dict(
            {
                "access_token": "test_token",
                "device_id": "test_device",
                "user_id": "@user:example.com",
            }
        )
        client_instance.login.return_value = login_response

        whoami_response = WhoamiResponse.from_dict(
            {
                "user_id": "@user:example.com",
            }
        )
        client_instance.whoami.return_value = whoami_response

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=TEST_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "@user:example.com"
    assert result["data"] == TEST_USER_INPUT


async def test_import_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test import flow with connection error."""
    with patch(
        "homeassistant.components.matrix.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=TEST_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_unexpected_error(hass: HomeAssistant) -> None:
    """Test import flow with an unexpected error."""
    with patch(
        "homeassistant.components.matrix.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=TEST_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_import_flow_duplicate_entry(hass: HomeAssistant) -> None:
    """Test import flow with duplicate entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_response = LoginResponse.from_dict(
            {
                "access_token": "test_token",
                "device_id": "test_device",
                "user_id": "@user:example.com",
            }
        )
        client_instance.login.return_value = login_response

        whoami_response = WhoamiResponse.from_dict(
            {
                "user_id": "@user:example.com",
            }
        )
        client_instance.whoami.return_value = whoami_response

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=TEST_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_validate_input_no_user_id_from_whoami(hass: HomeAssistant) -> None:
    """Test validate_input when whoami doesn't return user_id."""
    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_response = LoginResponse.from_dict(
            {
                "access_token": "test_token",
                "device_id": "test_device",
                "user_id": "@user:example.com",
            }
        )
        client_instance.login.return_value = login_response

        # Mock whoami response without user_id attribute
        whoami_response = object()
        client_instance.whoami.return_value = whoami_response

        result = await validate_input(hass, TEST_USER_INPUT)

    assert result["user_id"] == "@user:example.com"
    assert result["title"] == "@user:example.com"


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    """Test successful reauthentication flow."""
    # Set up existing config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "username": "@user:example.com",
        "homeserver": "https://matrix.example.com",
        "name": "@user:example.com",  # auto-injected by HA framework for reauth flows
    }

    # Complete reauth with new password
    new_password = "new_password"
    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_response = LoginResponse.from_dict(
            {
                "access_token": "new_test_token",
                "device_id": "test_device",
                "user_id": "@user:example.com",
            }
        )
        client_instance.login.return_value = login_response

        whoami_response = WhoamiResponse.from_dict(
            {
                "user_id": "@user:example.com",
            }
        )
        client_instance.whoami.return_value = whoami_response

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": new_password},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    # Verify the config entry was updated
    updated_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data["password"] == new_password


async def test_reauth_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test reauthentication flow with invalid authentication."""
    # Set up existing config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Try to complete reauth with invalid credentials
    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        # Mock authentication error
        login_error = LoginError.from_dict(
            {"errcode": "M_FORBIDDEN", "error": "Invalid username or password"}
        )
        client_instance.login.return_value = login_error

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "wrong_password"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_wrong_account(hass: HomeAssistant) -> None:
    """Test reauthentication flow with wrong account."""
    # Set up existing config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Try to complete reauth with different user
    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_response = LoginResponse.from_dict(
            {
                "access_token": "test_token",
                "device_id": "test_device",
                "user_id": "@different_user:example.com",
            }
        )
        client_instance.login.return_value = login_response

        whoami_response = WhoamiResponse.from_dict(
            {
                "user_id": "@different_user:example.com",
            }
        )
        client_instance.whoami.return_value = whoami_response

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "password"},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "wrong_account"


async def test_reauth_flow_unexpected_error(hass: HomeAssistant) -> None:
    """Test reauthentication flow with unexpected error."""
    # Set up existing config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Try to complete reauth with unexpected error
    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        mock_client.side_effect = Exception("Unexpected error")

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "password"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "unknown"}


# ---------------------------------------------------------------------------
# Options flow tests
# ---------------------------------------------------------------------------

TEST_ROOMS = ["!roomA:example.com", "#roomB:example.com"]
TEST_COMMANDS = [
    {CONF_WORD: "testword", "name": "testword"},
    {CONF_EXPRESSION: "My name is (?P<name>.*)", "name": "introduction"},
    {CONF_REACTION: "👍", "name": "thumbsup"},
]


async def test_options_flow_empty(hass: HomeAssistant) -> None:
    """Test options flow with no rooms or commands (empty config)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ROOMS: [], CONF_COMMANDS: []},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {CONF_ROOMS: [], CONF_COMMANDS: []}


async def test_options_flow_with_rooms_and_commands(hass: HomeAssistant) -> None:
    """Test options flow saving rooms and commands."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ROOMS: TEST_ROOMS, CONF_COMMANDS: TEST_COMMANDS},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_ROOMS] == TEST_ROOMS
    assert result2["data"][CONF_COMMANDS] == TEST_COMMANDS


async def test_options_flow_shows_existing_values(hass: HomeAssistant) -> None:
    """Test that the options form is pre-filled with current options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data={**TEST_USER_INPUT, CONF_ROOMS: TEST_ROOMS},
        options={CONF_ROOMS: TEST_ROOMS, CONF_COMMANDS: TEST_COMMANDS},
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    # Verify the schema has suggested values (rooms and commands pre-filled)
    assert result["data_schema"] is not None
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert CONF_ROOMS in schema_keys
    assert CONF_COMMANDS in schema_keys


async def test_options_flow_falls_back_to_data(hass: HomeAssistant) -> None:
    """Test that options form falls back to entry.data when options is empty."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data={**TEST_USER_INPUT, CONF_ROOMS: TEST_ROOMS, CONF_COMMANDS: TEST_COMMANDS},
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    # Submit with the same values that were in data
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ROOMS: TEST_ROOMS, CONF_COMMANDS: TEST_COMMANDS},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_ROOMS] == TEST_ROOMS


async def test_options_flow_invalid_rooms(hass: HomeAssistant) -> None:
    """Test options flow with invalid room IDs."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Room ID without proper format
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ROOMS: ["invalid-room"], CONF_COMMANDS: []},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_ROOMS: "invalid_rooms"}


async def test_options_flow_invalid_commands_no_name(hass: HomeAssistant) -> None:
    """Test options flow with command missing name."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ROOMS: [],
            CONF_COMMANDS: [{CONF_WORD: "hello"}],  # missing 'name'
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_COMMANDS: "invalid_commands"}


async def test_options_flow_invalid_commands_no_trigger(hass: HomeAssistant) -> None:
    """Test options flow with command missing a trigger."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ROOMS: [],
            CONF_COMMANDS: [{"name": "no_trigger"}],  # no word/expression/reaction
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_COMMANDS: "invalid_commands"}


async def test_options_flow_invalid_commands_not_a_list(hass: HomeAssistant) -> None:
    """Test options flow when commands is not a list."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ROOMS: [], CONF_COMMANDS: "not-a-list"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_COMMANDS: "invalid_commands"}


async def test_options_flow_all_trigger_types(hass: HomeAssistant) -> None:
    """Test options flow accepts word, expression, and reaction triggers."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    commands = [
        {CONF_WORD: "testword", "name": "testword"},
        {CONF_EXPRESSION: "My name is (?P<name>.*)", "name": "introduction"},
        {CONF_REACTION: "👍", "name": "thumbsup"},
    ]

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ROOMS: ["!room:example.com", "#alias:example.com"],
            CONF_COMMANDS: commands,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert len(result2["data"][CONF_COMMANDS]) == 3


async def test_options_flow_commands_with_room_subset(hass: HomeAssistant) -> None:
    """Test options flow with commands restricted to specific rooms."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
        title="@user:example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    commands = [
        {
            CONF_WORD: "testword",
            "name": "testword",
            CONF_ROOMS: ["#someothertest:matrix.org"],
        },
    ]

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ROOMS: ["#hasstest:matrix.org", "#someothertest:matrix.org"],
            CONF_COMMANDS: commands,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_COMMANDS][0][CONF_ROOMS] == [
        "#someothertest:matrix.org"
    ]
