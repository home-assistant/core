"""Test the Cync by GE config flow."""

from unittest.mock import AsyncMock, MagicMock

from pycync.exceptions import AuthFailedError, CyncError, TwoFactorRequiredError

from homeassistant import config_entries
from homeassistant.components.cync_by_ge.const import (
    CONF_ACCESS_TOKEN,
    CONF_AUTHORIZE_STRING,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_TWO_FACTOR_CODE,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "cync_by_ge-123456789"
    assert result["data"] == {
        CONF_USER_ID: 123456789,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: 3600,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_two_factor_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, client: MagicMock
) -> None:
    """Test we handle a request for a two factor code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Enter two factor code
    client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "123456",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "cync_by_ge-123456789"
    assert result["data"] == {
        CONF_USER_ID: 123456789,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: 3600,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_two_factor_bad_code(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, client: MagicMock
) -> None:
    """Test we handle a request for a two factor code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Enter two factor code
    client.login.side_effect = AuthFailedError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    # Enter two factor code
    client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "567890",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "cync_by_ge-123456789"
    assert result["data"] == {
        CONF_USER_ID: 123456789,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: 3600,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_two_factor_cant_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, client: MagicMock
) -> None:
    """Test we handle a request for a two factor code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Enter two factor code
    client.login.side_effect = CyncError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    # Enter two factor code
    client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "567890",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "cync_by_ge-123456789"
    assert result["data"] == {
        CONF_USER_ID: 123456789,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: 3600,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_two_factor_unknown_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, client: MagicMock
) -> None:
    """Test we handle a request for a two factor code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Enter two factor code
    client.login.side_effect = Exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    # Enter two factor code
    client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "567890",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "cync_by_ge-123456789"
    assert result["data"] == {
        CONF_USER_ID: 123456789,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: 3600,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, client: MagicMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client.login.side_effect = AuthFailedError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "cync_by_ge-123456789"
    assert result["data"] == {
        CONF_USER_ID: 123456789,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: 3600,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, client: MagicMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client.login.side_effect = CyncError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "cync_by_ge-123456789"
    assert result["data"] == {
        CONF_USER_ID: 123456789,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: 3600,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, client: MagicMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client.login.side_effect = Exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@testdomain.com",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "cync_by_ge-123456789"
    assert result["data"] == {
        CONF_USER_ID: 123456789,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: 3600,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1
