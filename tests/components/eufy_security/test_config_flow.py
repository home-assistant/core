"""Test the Eufy Security config flow."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from eufy_security import (
    CannotConnectError,
    CaptchaRequiredError,
    EufySecurityError,
    InvalidCaptchaError,
    InvalidCredentialsError,
)

from homeassistant import config_entries
from homeassistant.components.eufy_security.config_flow import EufySecurityConfigFlow
from homeassistant.components.eufy_security.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_flow_api: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test@example.com"
    # Check that required fields are present in data
    assert result2["data"][CONF_EMAIL] == "test@example.com"
    assert result2["data"][CONF_PASSWORD] == "test-password"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=InvalidCredentialsError("Invalid credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "wrong-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CannotConnectError("Connection failed"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_eufy_security_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle generic Eufy Security errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=EufySecurityError("API error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=RuntimeError("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_flow_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort when account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_captcha_required(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test CAPTCHA flow when required during initial login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # First login attempt triggers CAPTCHA
    mock_api = MagicMock()
    mock_api.token = "test-token"
    mock_api.token_expiration = datetime.now() + timedelta(days=1)
    mock_api.api_base = "https://mysecurity.eufylife.com"
    mock_api.get_crypto_state = MagicMock(
        return_value={"private_key": "0" * 64, "server_public_key": "0" * 64}
    )

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha123",
            captcha_image="data:image/png;base64,ABC123",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "captcha"
    assert "captcha_img" in result2["description_placeholders"]

    # Now solve the CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        return_value=mock_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "12345"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "test@example.com"


async def test_form_captcha_invalid(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test invalid CAPTCHA handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api = MagicMock()
    mock_api.token = "test-token"
    mock_api.token_expiration = datetime.now() + timedelta(days=1)
    mock_api.api_base = "https://mysecurity.eufylife.com"
    mock_api.get_crypto_state = MagicMock(
        return_value={"private_key": "0" * 64, "server_public_key": "0" * 64}
    )

    # First attempt triggers CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha123",
            captcha_image="data:image/png;base64,ABC123",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["step_id"] == "captcha"

    # Wrong CAPTCHA - server sends new CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "Wrong CAPTCHA",
            captcha_id="captcha456",
            captcha_image="data:image/png;base64,NEW123",
            api=mock_api,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "wrong"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "captcha"
    assert result3["errors"] == {"base": "invalid_captcha"}


async def test_form_captcha_invalid_no_new_captcha(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test invalid CAPTCHA when server doesn't provide new one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api = MagicMock()

    # First attempt triggers CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha123",
            captcha_image="data:image/png;base64,ABC123",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    # Wrong CAPTCHA - InvalidCaptchaError, then re-request triggers new CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=[
            InvalidCaptchaError("Invalid CAPTCHA"),
            CaptchaRequiredError(
                "CAPTCHA required",
                captcha_id="captcha789",
                captcha_image="data:image/png;base64,FRESH",
                api=mock_api,
            ),
        ],
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "wrong"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_captcha"}


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_flow_api: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauthentication flow."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "new-password",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert init_integration.data[CONF_PASSWORD] == "new-password"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauthentication flow with invalid auth."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=InvalidCredentialsError("Invalid credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "wrong-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauthentication flow with connection error."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CannotConnectError("Connection failed"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_eufy_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauthentication flow with generic Eufy error."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=EufySecurityError("API error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauthentication flow with unknown error."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=RuntimeError("Unexpected"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_flow_captcha_required(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauthentication flow when CAPTCHA is required."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    mock_api = MagicMock()
    mock_api.token = "new-token"
    mock_api.token_expiration = datetime.now() + timedelta(days=1)
    mock_api.api_base = "https://mysecurity.eufylife.com"
    mock_api.get_crypto_state = MagicMock(
        return_value={"private_key": "1" * 64, "server_public_key": "1" * 64}
    )

    # Reauth triggers CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha_reauth",
            captcha_image="data:image/png;base64,REAUTH",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reauth_captcha"

    # Solve CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        return_value=mock_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "solved"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"


async def test_reauth_captcha_invalid(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauth CAPTCHA flow with invalid CAPTCHA."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    mock_api = MagicMock()

    # Reauth triggers CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha_reauth",
            captcha_image="data:image/png;base64,REAUTH",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )

    # Wrong CAPTCHA - new CAPTCHA provided
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "Wrong CAPTCHA",
            captcha_id="captcha_new",
            captcha_image="data:image/png;base64,NEW",
            api=mock_api,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "wrong"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "reauth_captcha"
    assert result3["errors"] == {"base": "invalid_captcha"}


async def test_reauth_captcha_invalid_no_new_captcha(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauth CAPTCHA flow when server doesn't provide new CAPTCHA."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    mock_api = MagicMock()

    # Reauth triggers CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha_reauth",
            captcha_image="data:image/png;base64,REAUTH",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )

    # Wrong CAPTCHA - InvalidCaptchaError then re-request
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=[
            InvalidCaptchaError("Invalid CAPTCHA"),
            CaptchaRequiredError(
                "Fresh CAPTCHA",
                captcha_id="captcha_fresh",
                captcha_image="data:image/png;base64,FRESH",
                api=mock_api,
            ),
        ],
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "wrong"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_captcha"}


async def test_reauth_captcha_other_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauth CAPTCHA flow with various errors."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "password"},
        )

    # Test InvalidCredentialsError
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=InvalidCredentialsError("Bad creds"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "code"},
        )

    assert result3["errors"] == {"base": "invalid_auth"}


async def test_options_flow_no_cameras(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test options flow when no cameras are found."""
    # Clear cameras from runtime_data
    init_integration.runtime_data.devices["cameras"] = {}

    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert "No cameras found" in result["description_placeholders"]["camera_info"]


async def test_options_flow_configure_cameras(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test options flow to configure RTSP credentials."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    # Should go directly to camera step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "camera"
    assert "Front Door Camera" in result["description_placeholders"]["camera_name"]

    # Configure RTSP credentials for the camera
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "rtsp_username": "admin",
            "rtsp_password": "secret123",
        },
    )
    await hass.async_block_till_done()

    # With only one camera, should complete
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"]["rtsp_credentials"]["T1234567890"] == {
        "username": "admin",
        "password": "secret123",
    }


async def test_options_flow_skip_camera(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test options flow skipping RTSP configuration."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    # Leave fields empty to skip
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "rtsp_username": "",
            "rtsp_password": "",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    # Should not have credentials for this camera
    assert "T1234567890" not in result2["data"].get("rtsp_credentials", {})


async def test_options_flow_clear_existing_credentials(
    hass: HomeAssistant,
    mock_eufy_api: MagicMock,
    mock_camera: MagicMock,
    mock_station: MagicMock,
) -> None:
    """Test options flow clearing existing RTSP credentials."""
    # Create entry with existing RTSP credentials
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
        options={
            "rtsp_credentials": {
                "T1234567890": {"username": "old_user", "password": "old_pass"}
            }
        },
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    # Clear credentials by leaving empty
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"rtsp_username": "", "rtsp_password": ""},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert "T1234567890" not in result2["data"].get("rtsp_credentials", {})


async def test_captcha_img_tag_none(
    hass: HomeAssistant,
) -> None:
    """Test _get_captcha_img_tag returns empty string for None."""
    flow = EufySecurityConfigFlow()
    assert flow._get_captcha_img_tag(None) == ""


async def test_captcha_step_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test CAPTCHA step handles CannotConnectError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api = MagicMock()

    # First attempt triggers CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha123",
            captcha_image="data:image/png;base64,ABC123",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    # CAPTCHA step - CannotConnectError
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CannotConnectError("Connection failed"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "12345"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_captcha_step_eufy_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test CAPTCHA step handles EufySecurityError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api = MagicMock()

    # First attempt triggers CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha123",
            captcha_image="data:image/png;base64,ABC123",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    # CAPTCHA step - EufySecurityError
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=EufySecurityError("API error"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "12345"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_captcha_step_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test CAPTCHA step handles unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api = MagicMock()

    # First attempt triggers CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha123",
            captcha_image="data:image/png;base64,ABC123",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    # CAPTCHA step - Unknown error
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=RuntimeError("Unexpected"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "12345"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "unknown"}


async def test_captcha_step_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test CAPTCHA step handles InvalidCredentialsError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api = MagicMock()

    # First attempt triggers CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha123",
            captcha_image="data:image/png;base64,ABC123",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    # CAPTCHA step - InvalidCredentialsError
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=InvalidCredentialsError("Bad credentials"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "12345"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_reauth_captcha_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauth CAPTCHA step handles CannotConnectError."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "password"},
        )

    # Test CannotConnectError
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CannotConnectError("Connection failed"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "code"},
        )

    assert result3["errors"] == {"base": "cannot_connect"}


async def test_reauth_captcha_eufy_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauth CAPTCHA step handles EufySecurityError."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "password"},
        )

    # Test EufySecurityError
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=EufySecurityError("API error"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "code"},
        )

    assert result3["errors"] == {"base": "cannot_connect"}


async def test_reauth_captcha_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauth CAPTCHA step handles unknown errors."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    [result] = flows

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "password"},
        )

    # Test unknown error
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=RuntimeError("Unexpected"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "code"},
        )

    assert result3["errors"] == {"base": "unknown"}


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_flow_api: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfiguration flow."""
    result = await init_integration.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Use same email as existing entry (reconfigure doesn't allow changing account)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "new-password",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert init_integration.data[CONF_EMAIL] == "test@example.com"
    assert init_integration.data[CONF_PASSWORD] == "new-password"


async def test_reconfigure_flow_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with invalid auth."""
    result = await init_integration.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=InvalidCredentialsError("Invalid credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "wrong-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with connection error."""
    result = await init_integration.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CannotConnectError("Connection failed"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_eufy_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with Eufy error."""
    result = await init_integration.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=EufySecurityError("API error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with unknown error."""
    result = await init_integration.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=RuntimeError("Unexpected"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reconfigure_flow_captcha_required(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfiguration flow when CAPTCHA is required."""
    result = await init_integration.start_reconfigure_flow(hass)

    mock_api = MagicMock()
    mock_api.token = "new-token"
    mock_api.token_expiration = datetime.now() + timedelta(days=1)
    mock_api.api_base = "https://mysecurity.eufylife.com"
    mock_api.get_crypto_state = MagicMock(
        return_value={"private_key": "1" * 64, "server_public_key": "1" * 64}
    )

    # Reconfigure triggers CAPTCHA (use same email as existing entry)
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha_reconfig",
            captcha_image="data:image/png;base64,RECONFIG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "new-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure_captcha"

    # Solve CAPTCHA
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        return_value=mock_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "solved"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"


async def test_reconfigure_captcha_invalid(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfigure CAPTCHA flow with invalid CAPTCHA."""
    result = await init_integration.start_reconfigure_flow(hass)

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
        )

    # Wrong CAPTCHA - new CAPTCHA provided
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "Wrong CAPTCHA",
            captcha_id="captcha_new",
            captcha_image="data:image/png;base64,NEW",
            api=mock_api,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "wrong"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "reconfigure_captcha"
    assert result3["errors"] == {"base": "invalid_captcha"}


async def test_reconfigure_captcha_invalid_no_new_captcha(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfigure CAPTCHA flow when server doesn't provide new CAPTCHA."""
    result = await init_integration.start_reconfigure_flow(hass)

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
        )

    # Wrong CAPTCHA - InvalidCaptchaError then re-request
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=[
            InvalidCaptchaError("Invalid CAPTCHA"),
            CaptchaRequiredError(
                "Fresh CAPTCHA",
                captcha_id="captcha_fresh",
                captcha_image="data:image/png;base64,FRESH",
                api=mock_api,
            ),
        ],
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "wrong"},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_captcha"}


async def test_reconfigure_captcha_other_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfigure CAPTCHA flow with various errors."""
    result = await init_integration.start_reconfigure_flow(hass)

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
        )

    # Test InvalidCredentialsError
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=InvalidCredentialsError("Bad creds"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "code"},
        )

    assert result3["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_captcha_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfigure CAPTCHA step handles CannotConnectError."""
    result = await init_integration.start_reconfigure_flow(hass)

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
        )

    # Test CannotConnectError
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CannotConnectError("Connection failed"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "code"},
        )

    assert result3["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_captcha_eufy_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfigure CAPTCHA step handles EufySecurityError."""
    result = await init_integration.start_reconfigure_flow(hass)

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
        )

    # Test EufySecurityError
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=EufySecurityError("API error"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "code"},
        )

    assert result3["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_captcha_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reconfigure CAPTCHA step handles unknown errors."""
    result = await init_integration.start_reconfigure_flow(hass)

    mock_api = MagicMock()

    # Trigger CAPTCHA step
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=CaptchaRequiredError(
            "CAPTCHA required",
            captcha_id="captcha",
            captcha_image="data:image/png;base64,IMG",
            api=mock_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
        )

    # Test unknown error
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=RuntimeError("Unexpected"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"captcha_code": "code"},
        )

    assert result3["errors"] == {"base": "unknown"}
