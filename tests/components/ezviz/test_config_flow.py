"""Test the EZVIZ config flow."""

from unittest.mock import AsyncMock

from pyezvizapi.exceptions import (
    EzvizAuthVerificationCode,
    InvalidHost,
    InvalidURL,
    PyEzvizError,
)
import pytest

from homeassistant.components.ezviz.const import (
    ATTR_SERIAL,
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RFSESSION_ID,
    CONF_SESSION_ID,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, SOURCE_USER
from homeassistant.const import (
    CONF_CUSTOMIZE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_ezviz_client")
async def test_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
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


@pytest.mark.usefixtures("mock_ezviz_client")
async def test_user_custom_url(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
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


@pytest.mark.usefixtures("mock_ezviz_client", "mock_setup_entry")
async def test_async_step_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reauth step."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
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


@pytest.mark.usefixtures("mock_ezviz_client")
async def test_step_discovery_abort_if_cloud_account_missing(
    hass: HomeAssistant, mock_test_rtsp_auth: AsyncMock
) -> None:
    """Test discovery and confirm step, abort if cloud account was removed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={
            ATTR_SERIAL: "C666666",
            CONF_USERNAME: None,
            CONF_PASSWORD: None,
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ezviz_cloud_account_missing"


@pytest.mark.usefixtures("mock_ezviz_client", "mock_test_rtsp_auth")
async def test_step_reauth_abort_if_cloud_account_missing(
    hass: HomeAssistant, mock_camera_config_entry: MockConfigEntry
) -> None:
    """Test reauth and confirm step, abort if cloud account was removed."""

    mock_camera_config_entry.add_to_hass(hass)

    result = await mock_camera_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ezviz_cloud_account_missing"


@pytest.mark.usefixtures("mock_ezviz_client", "mock_test_rtsp_auth", "mock_setup_entry")
async def test_async_step_integration_discovery(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovery and confirm step."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={
            ATTR_SERIAL: "C666666",
            CONF_USERNAME: None,
            CONF_PASSWORD: None,
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PASSWORD: "test-pass",
        CONF_TYPE: ATTR_TYPE_CAMERA,
        CONF_USERNAME: "test-user",
    }
    assert result["result"].unique_id == "C666666"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test updating options."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.options[CONF_FFMPEG_ARGUMENTS] == DEFAULT_FFMPEG_ARGUMENTS
    assert mock_config_entry.options[CONF_TIMEOUT] == DEFAULT_TIMEOUT

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_FFMPEG_ARGUMENTS: "/H.264", CONF_TIMEOUT: 25},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FFMPEG_ARGUMENTS] == "/H.264"
    assert result["data"][CONF_TIMEOUT] == 25


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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_unknown_exception(
    hass: HomeAssistant, mock_ezviz_client: AsyncMock
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_custom_url_unknown_exception(
    hass: HomeAssistant, mock_ezviz_client: AsyncMock
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


async def test_async_step_integration_discovery_duplicate(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_test_rtsp_auth: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_camera_config_entry: MockConfigEntry,
) -> None:
    """Test discovery and confirm step."""
    mock_config_entry.add_to_hass(hass)
    mock_camera_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={
            ATTR_SERIAL: "C666666",
            CONF_USERNAME: None,
            CONF_PASSWORD: None,
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (InvalidURL, "invalid_host"),
        (InvalidHost, "invalid_host"),
        (EzvizAuthVerificationCode, "mfa_required"),
        (PyEzvizError, "invalid_auth"),
    ],
)
async def test_camera_errors(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_test_rtsp_auth: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test the camera flow with errors."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={
            ATTR_SERIAL: "C666666",
            CONF_USERNAME: None,
            CONF_PASSWORD: None,
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
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
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": error}

    mock_ezviz_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "C666666"
    assert result["data"] == {
        CONF_TYPE: ATTR_TYPE_CAMERA,
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "C666666"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_camera_unknown_error(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_test_rtsp_auth: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the camera flow with errors."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={
            ATTR_SERIAL: "C666666",
            CONF_USERNAME: None,
            CONF_PASSWORD: None,
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
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


@pytest.mark.usefixtures("mock_setup_entry")
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
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test the reauth step."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_unknown_exception(
    hass: HomeAssistant,
    mock_ezviz_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth step."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
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
