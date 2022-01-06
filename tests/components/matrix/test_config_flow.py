"""Tests for the Matrix config flow."""
from __future__ import annotations

from typing import Any, Final
from unittest.mock import patch

from matrix_client.errors import MatrixRequestError
from requests.exceptions import ConnectionError
from requests_mock import ANY
import voluptuous as vol

from homeassistant.components.matrix.config_flow import (
    CONFIG_FLOW_ADDITIONAL_SCHEMA,
    validate_input,
)
from homeassistant.components.matrix.const import (
    CONF_COMMANDS,
    CONF_EXPRESSION,
    CONF_HOMESERVER,
    CONF_ROOMS,
    CONF_WORD,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_BASE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
    FlowResult,
)

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT: Final[dict[str, Any]] = {
    CONF_HOMESERVER: "https://matrix-client.matrix.org",
    CONF_USERNAME: "@dummyuser:matrix.org",
    CONF_PASSWORD: "secret",
    CONF_VERIFY_SSL: True,
}

FIXTURE_ALTER_USER_INPUT: Final[dict[str, Any]] = {
    CONF_HOMESERVER: "https://mozilla.modular.im",
    CONF_USERNAME: "@foobar:mozilla.org",
    CONF_PASSWORD: "password",
    CONF_VERIFY_SSL: False,
}

FIXTURE_USER_INPUT_FROM_YAML: Final[dict[str, Any]] = {
    CONF_HOMESERVER: "https://matrix-client.matrix.org",
    CONF_USERNAME: "@dummyuser:matrix.org",
    CONF_PASSWORD: "secret",
    CONF_VERIFY_SSL: True,
    CONF_ROOMS: ["#matrix:matrix.org", "#general:mozilla.org"],
    CONF_COMMANDS: [
        {
            CONF_WORD: "ping",
            CONF_NAME: "ping",
            CONF_ROOMS: ["#matrix:matrix.org"],
        },
        {
            CONF_EXPRESSION: ".*hello.*",
            CONF_NAME: "hello",
            CONF_ROOMS: ["#general:mozilla.org"],
        },
    ],
}

FIXTURE_INVALID_USER_INPUT: Final[dict[str, Any]] = {
    CONF_HOMESERVER: "Any invalid URL",
    CONF_USERNAME: "dummyuser",
    CONF_PASSWORD: "secret",
    CONF_VERIFY_SSL: True,
}

FIXTURE_UNIQUE_ID: Final[str] = FIXTURE_USER_INPUT[CONF_USERNAME]
FIXTURE_ACCESS_TOKEN: Final[str] = "syt_dummytoken_dummytoken_dummytoken"


class DummyAuthWithToken:
    """An authentication class with the token property available."""

    def __init__(self, token: str) -> None:
        """Initialize the class."""
        self.token: str = token


class DummyAuthWithoutToken:
    """An authentication class without any token property."""

    def __init__(self) -> None:
        """Initialize the class."""
        pass


async def validate_login_result(result: FlowResult, user_input: dict[str, Any]):
    """Validate the login result matches the user input."""
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == user_input[CONF_USERNAME]
    assert result["data"][CONF_HOMESERVER] == user_input[CONF_HOMESERVER]
    assert result["data"][CONF_USERNAME] == user_input[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == user_input[CONF_PASSWORD]
    assert result["data"][CONF_VERIFY_SSL] == user_input[CONF_VERIFY_SSL]


async def finish_login(hass: HomeAssistant, previous_result: FlowResult):
    """Finish the login procedure."""
    dummy_auth: DummyAuthWithToken = DummyAuthWithToken(FIXTURE_ACCESS_TOKEN)

    with patch(
        "homeassistant.components.matrix.MatrixAuthentication.login",
        return_value=dummy_auth,
    ):
        result: FlowResult = await hass.config_entries.flow.async_configure(
            flow_id=previous_result["flow_id"],
            user_input=FIXTURE_USER_INPUT,
        )
        await hass.async_block_till_done()

    await validate_login_result(result, FIXTURE_USER_INPUT)


async def test_config_flow_schema(hass: HomeAssistant) -> None:
    """Test CONFIG_FLOW_ADDITIONAL_SCHEMA can verify the user input correctly."""
    try:
        CONFIG_FLOW_ADDITIONAL_SCHEMA(FIXTURE_USER_INPUT)
        CONFIG_FLOW_ADDITIONAL_SCHEMA(FIXTURE_ALTER_USER_INPUT)
    except vol.Invalid:
        # Shouldn't happen
        assert False

    try:
        await validate_input(hass, FIXTURE_INVALID_USER_INPUT)
    except vol.MultipleInvalid as ex:
        invalid_list: tuple = (e.path[0] for e in ex.errors)
        assert CONF_HOMESERVER in invalid_list
        assert CONF_USERNAME in invalid_list


async def test_import(hass: HomeAssistant):
    """Test that we can import a config entry."""
    dummy_auth: DummyAuthWithToken = DummyAuthWithToken(FIXTURE_ACCESS_TOKEN)

    with patch(
        "homeassistant.components.matrix.MatrixAuthentication.login",
        return_value=dummy_auth,
    ):
        result: FlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=FIXTURE_USER_INPUT_FROM_YAML,
        )
        await hass.async_block_till_done()

    await validate_login_result(result, FIXTURE_USER_INPUT_FROM_YAML)

    # Validate the options are imported.
    assert len(result["options"][CONF_ROOMS]) == len(
        FIXTURE_USER_INPUT_FROM_YAML[CONF_ROOMS]
    )
    for room_id in result["options"][CONF_ROOMS]:
        assert room_id in FIXTURE_USER_INPUT_FROM_YAML[CONF_ROOMS]

    assert len(result["options"][CONF_COMMANDS]) == len(
        FIXTURE_USER_INPUT_FROM_YAML[CONF_COMMANDS]
    )
    for command in result["options"][CONF_COMMANDS]:
        assert command in FIXTURE_USER_INPUT_FROM_YAML[CONF_COMMANDS]


async def test_login_success(hass: HomeAssistant) -> None:
    """Test successful flow provides entry creation data."""
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None
    )

    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    dummy_auth: DummyAuthWithToken = DummyAuthWithToken(FIXTURE_ACCESS_TOKEN)

    with patch(
        "homeassistant.components.matrix.MatrixAuthentication.login",
        return_value=dummy_auth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=FIXTURE_USER_INPUT
        )
        await hass.async_block_till_done()

    await validate_login_result(result2, FIXTURE_USER_INPUT)


async def test_login_success_with_local_token(hass: HomeAssistant) -> None:
    """Test successful flow provides entry creation data."""
    dummy_auth: DummyAuthWithoutToken = DummyAuthWithoutToken()

    with patch(
        "homeassistant.components.matrix.MatrixAuthentication.login",
        return_value=dummy_auth,
    ), patch(
        "homeassistant.components.matrix.MatrixAuthentication.auth_token",
        return_value=FIXTURE_ACCESS_TOKEN,
    ):
        result: FlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )
        await hass.async_block_till_done()

    await validate_login_result(result, FIXTURE_USER_INPUT)


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UNIQUE_ID,
        data=FIXTURE_USER_INPUT,
        title="Already configured",
    ).add_to_hass(hass)

    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=FIXTURE_ALTER_USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_connection_error(hass: HomeAssistant, requests_mock) -> None:
    """Test we show user form on connection error."""
    requests_mock.request(ANY, ANY, exc=ConnectionError())
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=FIXTURE_USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_BASE: "cannot_connect"}


async def test_password_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when password is wrong."""
    with patch(
        "homeassistant.components.matrix.config_flow.validate_input",
        side_effect=MatrixRequestError(code=401, content='{"errcode": "M_FORBIDDEN"}'),
    ):
        result: FlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}

    await finish_login(hass, result)


async def test_invalid_json_string(hass: HomeAssistant) -> None:
    """Test that errors are shown when username is invalid."""
    with patch(
        "homeassistant.components.matrix.config_flow.validate_input",
        side_effect=MatrixRequestError(code=401, content='{"noerrcode": "noerrcode"}'),
    ):
        result: FlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_BASE: "unknown"}

    await finish_login(hass, result)


async def test_username_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when username is invalid."""
    with patch(
        "homeassistant.components.matrix.config_flow.validate_input",
        side_effect=MatrixRequestError(
            code=401, content='{"errcode": "M_INVALID_USERNAME"}'
        ),
    ):
        result: FlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_USERNAME: "invalid_auth"}

    await finish_login(hass, result)


async def test_token_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when access token is invalid."""
    with patch(
        "homeassistant.components.matrix.config_flow.validate_input",
        side_effect=MatrixRequestError(
            code=401, content='{"errcode": "M_UNKNOWN_TOKEN"}'
        ),
    ):
        result: FlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_BASE: "invalid_access_token"}

    await finish_login(hass, result)


async def test_other_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when access token is invalid."""
    with patch(
        "homeassistant.components.matrix.config_flow.validate_input",
        side_effect=MatrixRequestError(
            code=401, content='{"errcode": "M_DUMMY_ERROR"}'
        ),
    ):
        result: FlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_BASE: "unknown"}

    await finish_login(hass, result)
