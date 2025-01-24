"""Test the EZVIZ config flow."""

from unittest.mock import AsyncMock

from pyezviz.exceptions import (
    EzvizAuthVerificationCode,
    InvalidHost,
    InvalidURL,
    PyEzvizError,
)
import pytest

from homeassistant.components.ezviz.const import (
    ATTR_TYPE_CLOUD,
    CONF_RFSESSION_ID,
    CONF_SESSION_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_CUSTOMIZE,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, start_reauth_flow


async def test_full_flow(
    hass: HomeAssistant, mock_ezviz_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_URL: "apiieu.ezvizlife.com",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_SESSION_ID: "fake_token",
        CONF_RFSESSION_ID: "fake_rf_token",
        CONF_URL: "apiieu.ezvizlife.com",
        CONF_TYPE: ATTR_TYPE_CLOUD,
    }
    assert result["result"].unique_id == "test-username"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (InvalidURL, "invalid_host"),
        (InvalidHost, "cannot_connect"),
        (EzvizAuthVerificationCode, "mfa_required"),
        (PyEzvizError, "invalid_auth"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_ezviz_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_URL: "apiieu.ezvizlife.com",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_ezviz_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_URL: "apiieu.ezvizlife.com",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_SESSION_ID: "fake_token",
        CONF_RFSESSION_ID: "fake_rf_token",
        CONF_URL: "apiieu.ezvizlife.com",
        CONF_TYPE: ATTR_TYPE_CLOUD,
    }
    assert result["result"].unique_id == "test-username"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_unknown_exception(
    hass: HomeAssistant, mock_ezviz_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_ezviz_client.login.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_URL: "apiieu.ezvizlife.com",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_user_custom_url(
    hass: HomeAssistant, mock_ezviz_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test custom url step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_URL: CONF_CUSTOMIZE,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SESSION_ID: "fake_token",
        CONF_RFSESSION_ID: "fake_rf_token",
        CONF_URL: "apiieu.ezvizlife.com",
        CONF_TYPE: ATTR_TYPE_CLOUD,
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (InvalidURL, "invalid_host"),
        (InvalidHost, "cannot_connect"),
        (EzvizAuthVerificationCode, "mfa_required"),
        (PyEzvizError, "invalid_auth"),
    ],
)
async def test_user_custom_url_errors(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_ezviz_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_URL: CONF_CUSTOMIZE,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {"base": error}

    mock_ezviz_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_SESSION_ID: "fake_token",
        CONF_RFSESSION_ID: "fake_rf_token",
        CONF_URL: "apiieu.ezvizlife.com",
        CONF_TYPE: ATTR_TYPE_CLOUD,
    }
    assert result["result"].unique_id == "test-username"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_custom_url_unknown_exception(
    hass: HomeAssistant, mock_ezviz_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_ezviz_client.login.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_URL: CONF_CUSTOMIZE,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_already_configured(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the flow when the account is already configured."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_account"


async def test_async_step_reauth(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth step."""
    mock_config_entry.add_to_hass(hass)

    result = await start_reauth_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (InvalidURL, "invalid_host"),
        (InvalidHost, "invalid_host"),
        (EzvizAuthVerificationCode, "mfa_required"),
        (PyEzvizError, "invalid_auth"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test the reauth step."""
    mock_config_entry.add_to_hass(hass)

    result = await start_reauth_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    mock_ezviz_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_ezviz_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_unknown_exception(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth step."""
    mock_config_entry.add_to_hass(hass)

    result = await start_reauth_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    mock_ezviz_client.login.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


# async def test_step_reauth_abort_if_cloud_account_missing(hass: HomeAssistant) -> None:
#     """Test reauth and confirm step, abort if cloud account was removed."""
#
#     entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT_VALIDATE)
#     entry.add_to_hass(hass)
#
#     result = await entry.start_reauth_flow(hass)
#     assert result["type"] is FlowResultType.ABORT
#     assert result["reason"] == "ezviz_cloud_account_missing"


# async def test_step_discovery_abort_if_cloud_account_missing(
#     hass: HomeAssistant,
# ) -> None:
#     """Test discovery and confirm step, abort if cloud account was removed."""
#
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data=DISCOVERY_INFO
#     )
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {}
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#         },
#     )
#     await hass.async_block_till_done()
#
#     assert result["type"] is FlowResultType.ABORT
#     assert result["reason"] == "ezviz_cloud_account_missing"
#
#

#
#
# @pytest.mark.usefixtures("ezviz_config_flow", "ezviz_test_rtsp_config_flow")
# async def test_async_step_integration_discovery(hass: HomeAssistant) -> None:
#     """Test discovery and confirm step."""
#     with patch("homeassistant.components.ezviz.PLATFORMS_BY_TYPE", []):
#         await init_integration(hass)
#
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data=DISCOVERY_INFO
#     )
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {}
#
#     with patch_async_setup_entry() as mock_setup_entry:
#         result = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             {
#                 CONF_USERNAME: "test-user",
#                 CONF_PASSWORD: "test-pass",
#             },
#         )
#     await hass.async_block_till_done()
#
#     assert result["type"] is FlowResultType.CREATE_ENTRY
#     assert result["data"] == {
#         CONF_PASSWORD: "test-pass",
#         CONF_TYPE: ATTR_TYPE_CAMERA,
#         CONF_USERNAME: "test-user",
#     }
#
#     assert len(mock_setup_entry.mock_calls) == 1
#
#
# async def test_options_flow(hass: HomeAssistant) -> None:
#     """Test updating options."""
#     with patch_async_setup_entry() as mock_setup_entry:
#         entry = await init_integration(hass)
#
#         assert entry.options[CONF_FFMPEG_ARGUMENTS] == DEFAULT_FFMPEG_ARGUMENTS
#         assert entry.options[CONF_TIMEOUT] == DEFAULT_TIMEOUT
#
#         result = await hass.config_entries.options.async_init(entry.entry_id)
#         assert result["type"] is FlowResultType.FORM
#         assert result["step_id"] == "init"
#         assert result["errors"] is None
#
#         result = await hass.config_entries.options.async_configure(
#             result["flow_id"],
#             user_input={CONF_FFMPEG_ARGUMENTS: "/H.264", CONF_TIMEOUT: 25},
#         )
#         await hass.async_block_till_done()
#
#     assert result["type"] is FlowResultType.CREATE_ENTRY
#     assert result["data"][CONF_FFMPEG_ARGUMENTS] == "/H.264"
#     assert result["data"][CONF_TIMEOUT] == 25
#
#     assert len(mock_setup_entry.mock_calls) == 1
#
#
# async def test_user_form_exception(
#     hass: HomeAssistant, ezviz_config_flow: MagicMock
# ) -> None:
#     """Test we handle exception on user form."""
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": SOURCE_USER}
#     )
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user"
#     assert result["errors"] == {}
#
#     ezviz_config_flow.side_effect = PyEzvizError
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         USER_INPUT_VALIDATE,
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user"
#     assert result["errors"] == {"base": "invalid_auth"}
#
#     ezviz_config_flow.side_effect = InvalidURL
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         USER_INPUT_VALIDATE,
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user"
#     assert result["errors"] == {"base": "invalid_host"}
#
#     ezviz_config_flow.side_effect = EzvizAuthVerificationCode
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         USER_INPUT_VALIDATE,
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user"
#     assert result["errors"] == {"base": "mfa_required"}
#
#     ezviz_config_flow.side_effect = HTTPError
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         USER_INPUT_VALIDATE,
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user"
#     assert result["errors"] == {"base": "invalid_auth"}
#
#     ezviz_config_flow.side_effect = Exception
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         USER_INPUT_VALIDATE,
#     )
#
#     assert result["type"] is FlowResultType.ABORT
#     assert result["reason"] == "unknown"
#
#
# async def test_discover_exception_step1(
#     hass: HomeAssistant,
#     ezviz_config_flow: MagicMock,
# ) -> None:
#     """Test we handle unexpected exception on discovery."""
#     with patch("homeassistant.components.ezviz.PLATFORMS_BY_TYPE", []):
#         await init_integration(hass)
#
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN,
#         context={"source": SOURCE_INTEGRATION_DISCOVERY},
#         data={ATTR_SERIAL: "C66666", CONF_IP_ADDRESS: "test-ip"},
#     )
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {}
#
#     # Test Step 1
#     ezviz_config_flow.side_effect = PyEzvizError
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#         },
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {"base": "invalid_auth"}
#
#     ezviz_config_flow.side_effect = InvalidURL
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#         },
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {"base": "invalid_host"}
#
#     ezviz_config_flow.side_effect = HTTPError
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#         },
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {"base": "invalid_auth"}
#
#     ezviz_config_flow.side_effect = EzvizAuthVerificationCode
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#         },
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {"base": "mfa_required"}
#
#     ezviz_config_flow.side_effect = Exception
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#         },
#     )
#
#     assert result["type"] is FlowResultType.ABORT
#     assert result["reason"] == "unknown"
#
#
# @pytest.mark.usefixtures("ezviz_config_flow")
# async def test_discover_exception_step3(
#     hass: HomeAssistant, ezviz_test_rtsp_config_flow: MagicMock
# ) -> None:
#     """Test we handle unexpected exception on discovery."""
#     with patch("homeassistant.components.ezviz.PLATFORMS_BY_TYPE", []):
#         await init_integration(hass)
#
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN,
#         context={"source": SOURCE_INTEGRATION_DISCOVERY},
#         data={ATTR_SERIAL: "C66666", CONF_IP_ADDRESS: "test-ip"},
#     )
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {}
#
#     # Test Step 3
#     ezviz_test_rtsp_config_flow.side_effect = AuthTestResultFailed
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#         },
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {"base": "invalid_auth"}
#
#     ezviz_test_rtsp_config_flow.side_effect = InvalidHost
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#         },
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "confirm"
#     assert result["errors"] == {"base": "invalid_host"}
#
#     ezviz_test_rtsp_config_flow.side_effect = Exception
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#         },
#     )
#
#     assert result["type"] is FlowResultType.ABORT
#     assert result["reason"] == "unknown"
#
#
# async def test_user_custom_url_exception(
#     hass: HomeAssistant, ezviz_config_flow: MagicMock
# ) -> None:
#     """Test we handle unexpected exception."""
#     ezviz_config_flow.side_effect = PyEzvizError()
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": SOURCE_USER}
#     )
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-user",
#             CONF_PASSWORD: "test-pass",
#             CONF_URL: CONF_CUSTOMIZE,
#         },
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user_custom_url"
#     assert result["errors"] == {}
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {CONF_URL: "test-user"},
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user_custom_url"
#     assert result["errors"] == {"base": "invalid_auth"}
#
#     ezviz_config_flow.side_effect = InvalidURL
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {CONF_URL: "test-user"},
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user_custom_url"
#     assert result["errors"] == {"base": "invalid_host"}
#
#     ezviz_config_flow.side_effect = HTTPError
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {CONF_URL: "test-user"},
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user_custom_url"
#     assert result["errors"] == {"base": "invalid_auth"}
#
#     ezviz_config_flow.side_effect = EzvizAuthVerificationCode
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {CONF_URL: "test-user"},
#     )
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user_custom_url"
#     assert result["errors"] == {"base": "mfa_required"}
#
#     ezviz_config_flow.side_effect = Exception
#
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {CONF_URL: "test-user"},
#     )
#
#     assert result["type"] is FlowResultType.ABORT
#     assert result["reason"] == "unknown"
#
#
# async def test_async_step_reauth_exception(
#     hass: HomeAssistant, ezviz_config_flow: MagicMock
# ) -> None:
#     """Test the reauth step exceptions."""
#
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": SOURCE_USER}
#     )
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "user"
#     assert result["errors"] == {}
#
#     with patch_async_setup_entry() as mock_setup_entry:
#         result = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             USER_INPUT_VALIDATE,
#         )
#     await hass.async_block_till_done()
#
#     assert result["type"] is FlowResultType.CREATE_ENTRY
#     assert result["title"] == "test-username"
#     assert result["data"] == {**API_LOGIN_RETURN_VALIDATE}
#
#     assert len(mock_setup_entry.mock_calls) == 1
#
#     new_entry = hass.config_entries.async_entries(DOMAIN)[0]
#     result = await start_reauth_flow(hass, new_entry)
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "reauth_confirm"
#     assert result["errors"] == {}
#
#     ezviz_config_flow.side_effect = InvalidURL()
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-username",
#             CONF_PASSWORD: "test-password",
#         },
#     )
#     await hass.async_block_till_done()
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "reauth_confirm"
#     assert result["errors"] == {"base": "invalid_host"}
#
#     ezviz_config_flow.side_effect = InvalidHost()
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-username",
#             CONF_PASSWORD: "test-password",
#         },
#     )
#     await hass.async_block_till_done()
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "reauth_confirm"
#     assert result["errors"] == {"base": "invalid_host"}
#
#     ezviz_config_flow.side_effect = EzvizAuthVerificationCode()
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-username",
#             CONF_PASSWORD: "test-password",
#         },
#     )
#     await hass.async_block_till_done()
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "reauth_confirm"
#     assert result["errors"] == {"base": "mfa_required"}
#
#     ezviz_config_flow.side_effect = PyEzvizError()
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-username",
#             CONF_PASSWORD: "test-password",
#         },
#     )
#     await hass.async_block_till_done()
#
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "reauth_confirm"
#     assert result["errors"] == {"base": "invalid_auth"}
#
#     ezviz_config_flow.side_effect = Exception()
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             CONF_USERNAME: "test-username",
#             CONF_PASSWORD: "test-password",
#         },
#     )
#     await hass.async_block_till_done()
#
#     assert result["type"] is FlowResultType.ABORT
#     assert result["reason"] == "unknown"
