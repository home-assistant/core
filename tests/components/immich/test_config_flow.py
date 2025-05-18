"""Test the Immich config flow."""

from unittest.mock import DEFAULT, AsyncMock, Mock, patch

from aiohttp import ClientError
from aioimmich.exceptions import ImmichUnauthorizedError

from homeassistant.components.immich.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG_ENTRY_DATA, MOCK_USER_DATA

from tests.common import MockConfigEntry

MOCK_CONFIG_FLOW_SIDE_EFFECTS = [
    ImmichUnauthorizedError(
        {
            "message": "Invalid API key",
            "error": "Unauthenticated",
            "statusCode": 401,
            "correlationId": "abcdefg",
        }
    ),
    ClientError,
    Exception("Unknown error"),
    DEFAULT,
    DEFAULT,
]


async def test_step_user(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_immich: Mock
) -> None:
    """Test a user initiated config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.immich.config_flow.Immich",
            return_value=mock_immich,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user @ localhost"
    assert result["data"] == MOCK_CONFIG_ENTRY_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_step_user_error_handling(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_immich: Mock
) -> None:
    """Test a user initiated config flow with errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.immich.config_flow.Immich",
            return_value=mock_immich,
        ),
    ):
        mock_immich.users.async_get_my_user.side_effect = MOCK_CONFIG_FLOW_SIDE_EFFECTS

        # Test invalid auth
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}

        # Test connection error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

        # Test unknown error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}

        # Test invalid url
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_USER_DATA, CONF_URL: "hts://invalid"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"url": "invalid_url"}

        # Test successful connection
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user @ localhost"
    assert result["data"] == MOCK_CONFIG_ENTRY_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_already_configured(hass: HomeAssistant, mock_immich: Mock) -> None:
    """Test starting a flow by user when already configured."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_ENTRY_DATA, unique_id="user_id"
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.immich.config_flow.Immich",
            return_value=mock_immich,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_immich: Mock
) -> None:
    """Test reauthentication flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_ENTRY_DATA, unique_id="user_id"
    )
    mock_config.add_to_hass(hass)
    result = await mock_config.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.immich.config_flow.Immich",
            return_value=mock_immich,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "other_fake_api_key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config.data[CONF_API_KEY] == "other_fake_api_key"


async def test_reauth_flow_error_handling(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_immich: Mock
) -> None:
    """Test reauthentication flow with errors."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_ENTRY_DATA, unique_id="user_id"
    )
    mock_config.add_to_hass(hass)
    result = await mock_config.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.immich.config_flow.Immich",
            return_value=mock_immich,
        ),
    ):
        mock_immich.users.async_get_my_user.side_effect = MOCK_CONFIG_FLOW_SIDE_EFFECTS

        # Test invalid auth
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "other_fake_api_key",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_auth"}

        # Test connection error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "other_fake_api_key",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}

        # Test unknown error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "other_fake_api_key",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "unknown"}

        # Test successful connection
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "other_fake_api_key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config.data[CONF_API_KEY] == "other_fake_api_key"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_mismatch(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_immich: Mock
) -> None:
    """Test reauthentication flow with mis-matching unique id."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_ENTRY_DATA, unique_id="some_other_users_id"
    )
    mock_config.add_to_hass(hass)
    result = await mock_config.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.immich.config_flow.Immich",
            return_value=mock_immich,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "other_fake_api_key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
