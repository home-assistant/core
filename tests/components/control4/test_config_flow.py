"""Test the Control4 config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp.client_exceptions import ClientError
from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import BadCredentials, NotFound, Unauthorized

from homeassistant import config_entries
from homeassistant.components.control4.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_HOST, MOCK_PASSWORD, MOCK_USERNAME

from tests.common import MockConfigEntry


def _get_mock_c4_account():
    c4_account_mock = AsyncMock(C4Account)

    c4_account_mock.getAccountControllers.return_value = {
        "controllerCommonName": "control4_model_00AA00AA00AA",
        "href": "https://apis.control4.com/account/v3/rest/accounts/000000",
        "name": "Name",
    }

    c4_account_mock.getDirectorBearerToken.return_value = {"token": "token"}

    return c4_account_mock


def _get_mock_c4_director():
    c4_director_mock = AsyncMock(C4Director)
    c4_director_mock.getAllItemInfo.return_value = {}

    return c4_director_mock


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    c4_account = _get_mock_c4_account()
    c4_director = _get_mock_c4_director()
    with (
        patch(
            "homeassistant.components.control4.config_flow.C4Account",
            return_value=c4_account,
        ),
        patch(
            "homeassistant.components.control4.config_flow.C4Director",
            return_value=c4_director,
        ),
        patch(
            "homeassistant.components.control4.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "control4_model_00AA00AA00AA"
    assert result2["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        "controller_unique_id": "control4_model_00AA00AA00AA",
    }
    assert result2["result"].unique_id == "00:aa:00:aa:00:aa"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_credentials_invalid(hass: HomeAssistant) -> None:
    """Test we handle invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.control4.config_flow.C4Account",
        side_effect=BadCredentials("Invalid username or password"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "credentials_invalid"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle auth failure from the API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Use realistic JSON error format that pyControl4 returns
    json_error = (
        '{"C4ErrorResponse": {"code":401,"message":"Permission denied","subCode":0}}'
    )
    with patch(
        "homeassistant.components.control4.config_flow.C4Account",
        side_effect=Unauthorized(json_error),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "api_auth_failed"}
    assert result2["description_placeholders"]["error"] == "Permission denied"


async def test_form_controller_not_found(hass: HomeAssistant) -> None:
    """Test we handle controller not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.control4.config_flow.C4Account",
        side_effect=NotFound("No controller found"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "controller_not_found"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle an unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.control4.config_flow.C4Account",
        side_effect=ValueError("message"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_api_missing_controller_key(hass: HomeAssistant) -> None:
    """Test we handle missing controller key in API response."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock account that returns response missing "controllerCommonName"
    c4_account = AsyncMock(C4Account)
    c4_account.getAccountControllers.return_value = {"unexpected": "data"}

    with patch(
        "homeassistant.components.control4.config_flow.C4Account",
        return_value=c4_account,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_director_auth_failed(hass: HomeAssistant) -> None:
    """Test we handle director auth failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    c4_account = _get_mock_c4_account()
    with (
        patch(
            "homeassistant.components.control4.config_flow.C4Account",
            return_value=c4_account,
        ),
        patch(
            "homeassistant.components.control4.config_flow.C4Director",
            side_effect=Unauthorized("Director rejected token"),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "director_auth_failed"}


async def test_form_cannot_connect_client_error(hass: HomeAssistant) -> None:
    """Test we handle client connection error to director."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    c4_account = _get_mock_c4_account()
    with (
        patch(
            "homeassistant.components.control4.config_flow.C4Account",
            return_value=c4_account,
        ),
        patch(
            "homeassistant.components.control4.config_flow.C4Director",
            side_effect=ClientError("Connection refused"),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect_timeout(hass: HomeAssistant) -> None:
    """Test we handle timeout connecting to director."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    c4_account = _get_mock_c4_account()
    with (
        patch(
            "homeassistant.components.control4.config_flow.C4Account",
            return_value=c4_account,
        ),
        patch(
            "homeassistant.components.control4.config_flow.C4Director",
            side_effect=TimeoutError("Connection timed out"),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_director_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception from director."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    c4_account = _get_mock_c4_account()
    with (
        patch(
            "homeassistant.components.control4.config_flow.C4Account",
            return_value=c4_account,
        ),
        patch(
            "homeassistant.components.control4.config_flow.C4Director",
            side_effect=RuntimeError("Unexpected error"),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_option_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 4},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL: 4,
    }


async def test_option_flow_defaults(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    }
