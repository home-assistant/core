"""Test the EZVIZ config flow."""

from unittest.mock import patch

from pyezviz.exceptions import (
    AuthTestResultFailed,
    EzvizAuthVerificationCode,
    HTTPError,
    InvalidHost,
    InvalidURL,
    PyEzvizError,
)

from homeassistant.components.ezviz.const import (
    ATTR_SERIAL,
    ATTR_TYPE_CAMERA,
    CONF_FFMPEG_ARGUMENTS,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_REAUTH,
    SOURCE_USER,
)
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

from . import (
    API_LOGIN_RETURN_VALIDATE,
    DISCOVERY_INFO,
    USER_INPUT_VALIDATE,
    _patch_async_setup_entry,
    init_integration,
)


async def test_user_form(hass: HomeAssistant, ezviz_config_flow) -> None:
    """Test the user initiated form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT_VALIDATE,
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {**API_LOGIN_RETURN_VALIDATE}

    assert len(mock_setup_entry.mock_calls) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_account"


async def test_user_custom_url(hass: HomeAssistant, ezviz_config_flow) -> None:
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

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "test-user"},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == API_LOGIN_RETURN_VALIDATE

    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_reauth(hass: HomeAssistant, ezviz_config_flow) -> None:
    """Test the reauth step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT_VALIDATE,
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {**API_LOGIN_RETURN_VALIDATE}

    assert len(mock_setup_entry.mock_calls) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=USER_INPUT_VALIDATE
    )
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
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_step_discovery_abort_if_cloud_account_missing(
    hass: HomeAssistant,
) -> None:
    """Test discovery and confirm step, abort if cloud account was removed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data=DISCOVERY_INFO
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
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ezviz_cloud_account_missing"


async def test_step_reauth_abort_if_cloud_account_missing(hass: HomeAssistant) -> None:
    """Test reauth and confirm step, abort if cloud account was removed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=USER_INPUT_VALIDATE
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ezviz_cloud_account_missing"


async def test_async_step_integration_discovery(
    hass: HomeAssistant, ezviz_config_flow, ezviz_test_rtsp_config_flow
) -> None:
    """Test discovery and confirm step."""
    with patch("homeassistant.components.ezviz.PLATFORMS_BY_TYPE", []):
        await init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data=DISCOVERY_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-user",
                CONF_PASSWORD: "test-pass",
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PASSWORD: "test-pass",
        CONF_TYPE: ATTR_TYPE_CAMERA,
        CONF_USERNAME: "test-user",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options."""
    with _patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        assert entry.options[CONF_FFMPEG_ARGUMENTS] == DEFAULT_FFMPEG_ARGUMENTS
        assert entry.options[CONF_TIMEOUT] == DEFAULT_TIMEOUT

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_FFMPEG_ARGUMENTS: "/H.264", CONF_TIMEOUT: 25},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FFMPEG_ARGUMENTS] == "/H.264"
    assert result["data"][CONF_TIMEOUT] == 25

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_exception(hass: HomeAssistant, ezviz_config_flow) -> None:
    """Test we handle exception on user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    ezviz_config_flow.side_effect = PyEzvizError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_VALIDATE,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_config_flow.side_effect = InvalidURL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_VALIDATE,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}

    ezviz_config_flow.side_effect = EzvizAuthVerificationCode

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_VALIDATE,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "mfa_required"}

    ezviz_config_flow.side_effect = HTTPError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_VALIDATE,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_VALIDATE,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_discover_exception_step1(
    hass: HomeAssistant,
    ezviz_config_flow,
) -> None:
    """Test we handle unexpected exception on discovery."""
    with patch("homeassistant.components.ezviz.PLATFORMS_BY_TYPE", []):
        await init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={ATTR_SERIAL: "C66666", CONF_IP_ADDRESS: "test-ip"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    # Test Step 1
    ezviz_config_flow.side_effect = PyEzvizError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_config_flow.side_effect = InvalidURL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "invalid_host"}

    ezviz_config_flow.side_effect = HTTPError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_config_flow.side_effect = EzvizAuthVerificationCode

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "mfa_required"}

    ezviz_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_discover_exception_step3(
    hass: HomeAssistant,
    ezviz_config_flow,
    ezviz_test_rtsp_config_flow,
) -> None:
    """Test we handle unexpected exception on discovery."""
    with patch("homeassistant.components.ezviz.PLATFORMS_BY_TYPE", []):
        await init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={ATTR_SERIAL: "C66666", CONF_IP_ADDRESS: "test-ip"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    # Test Step 3
    ezviz_test_rtsp_config_flow.side_effect = AuthTestResultFailed

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_test_rtsp_config_flow.side_effect = InvalidHost

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "invalid_host"}

    ezviz_test_rtsp_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_user_custom_url_exception(
    hass: HomeAssistant, ezviz_config_flow
) -> None:
    """Test we handle unexpected exception."""
    ezviz_config_flow.side_effect = PyEzvizError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
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
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_config_flow.side_effect = InvalidURL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {"base": "invalid_host"}

    ezviz_config_flow.side_effect = HTTPError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_config_flow.side_effect = EzvizAuthVerificationCode

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {"base": "mfa_required"}

    ezviz_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_async_step_reauth_exception(
    hass: HomeAssistant, ezviz_config_flow
) -> None:
    """Test the reauth step exceptions."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT_VALIDATE,
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {**API_LOGIN_RETURN_VALIDATE}

    assert len(mock_setup_entry.mock_calls) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=USER_INPUT_VALIDATE
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    ezviz_config_flow.side_effect = InvalidURL()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_host"}

    ezviz_config_flow.side_effect = InvalidHost()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_host"}

    ezviz_config_flow.side_effect = EzvizAuthVerificationCode()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "mfa_required"}

    ezviz_config_flow.side_effect = PyEzvizError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_config_flow.side_effect = Exception()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"
