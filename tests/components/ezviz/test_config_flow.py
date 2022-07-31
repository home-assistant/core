"""Test the Ezviz config flow."""

from unittest.mock import patch

from pyezviz.exceptions import (
    AuthTestResultFailed,
    HTTPError,
    InvalidHost,
    InvalidURL,
    PyEzvizError,
)

from homeassistant.components.ezviz.const import (
    ATTR_SERIAL,
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
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
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DISCOVERY_INFO,
    USER_INPUT,
    USER_INPUT_VALIDATE,
    _patch_async_setup_entry,
    init_integration,
)


async def test_user_form(hass, ezviz_config_flow):
    """Test the user initiated form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT_VALIDATE,
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {**USER_INPUT}

    assert len(mock_setup_entry.mock_calls) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured_account"


async def test_user_custom_url(hass, ezviz_config_flow):
    """Test custom url step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-user", CONF_PASSWORD: "test-pass", CONF_URL: "customize"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {}

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "test-user"},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PASSWORD: "test-pass",
        CONF_TYPE: ATTR_TYPE_CLOUD,
        CONF_URL: "test-user",
        CONF_USERNAME: "test-user",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_step_discovery_abort_if_cloud_account_missing(hass):
    """Test discovery and confirm step, abort if cloud account was removed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data=DISCOVERY_INFO
    )
    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "ezviz_cloud_account_missing"


async def test_async_step_integration_discovery(
    hass, ezviz_config_flow, ezviz_test_rtsp_config_flow
):
    """Test discovery and confirm step."""
    with patch("homeassistant.components.ezviz.PLATFORMS", []):
        await init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data=DISCOVERY_INFO
    )
    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PASSWORD: "test-pass",
        CONF_TYPE: ATTR_TYPE_CAMERA,
        CONF_USERNAME: "test-user",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass):
    """Test updating options."""
    with _patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        assert entry.options[CONF_FFMPEG_ARGUMENTS] == DEFAULT_FFMPEG_ARGUMENTS
        assert entry.options[CONF_TIMEOUT] == DEFAULT_TIMEOUT

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_FFMPEG_ARGUMENTS: "/H.264", CONF_TIMEOUT: 25},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FFMPEG_ARGUMENTS] == "/H.264"
    assert result["data"][CONF_TIMEOUT] == 25

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_exception(hass, ezviz_config_flow):
    """Test we handle exception on user form."""
    ezviz_config_flow.side_effect = PyEzvizError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_VALIDATE,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_config_flow.side_effect = InvalidURL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_VALIDATE,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}

    ezviz_config_flow.side_effect = HTTPError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_VALIDATE,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    ezviz_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_VALIDATE,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_discover_exception_step1(
    hass,
    ezviz_config_flow,
):
    """Test we handle unexpected exception on discovery."""
    with patch("homeassistant.components.ezviz.PLATFORMS", []):
        await init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={ATTR_SERIAL: "C66666", CONF_IP_ADDRESS: "test-ip"},
    )
    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "invalid_host"}

    ezviz_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_discover_exception_step3(
    hass,
    ezviz_config_flow,
    ezviz_test_rtsp_config_flow,
):
    """Test we handle unexpected exception on discovery."""
    with patch("homeassistant.components.ezviz.PLATFORMS", []):
        await init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={ATTR_SERIAL: "C66666", CONF_IP_ADDRESS: "test-ip"},
    )
    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_user_custom_url_exception(hass, ezviz_config_flow):
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {"base": "invalid_auth"}

    ezviz_config_flow.side_effect = InvalidURL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {"base": "invalid_host"}

    ezviz_config_flow.side_effect = HTTPError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_custom_url"
    assert result["errors"] == {"base": "cannot_connect"}

    ezviz_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "test-user"},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"
