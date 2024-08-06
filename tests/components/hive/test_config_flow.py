"""Test the Hive config flow."""

from unittest.mock import patch

from apyhiveapi.helper import hive_exceptions

from homeassistant import config_entries
from homeassistant.components.hive.const import CONF_CODE, CONF_DEVICE_NAME, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USERNAME = "username@home-assistant.com"
UPDATED_USERNAME = "updated_username@home-assistant.com"
PASSWORD = "test-password"
UPDATED_PASSWORD = "updated-password"
INCORRECT_PASSWORD = "incorrect-password"
SCAN_INTERVAL = 120
UPDATED_SCAN_INTERVAL = 60
DEVICE_NAME = "Test Home Assistant"
MFA_CODE = "1234"
MFA_RESEND_CODE = "0000"
MFA_INVALID_CODE = "HIVE"


async def test_import_flow(hass: HomeAssistant) -> None:
    """Check import flow."""

    with (
        patch(
            "homeassistant.components.hive.config_flow.Auth.login",
            return_value={
                "ChallengeName": "SUCCESS",
                "AuthenticationResult": {
                    "RefreshToken": "mock-refresh-token",
                    "AccessToken": "mock-access-token",
                },
            },
        ),
        patch(
            "homeassistant.components.hive.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.hive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"] == {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
        "tokens": {
            "AuthenticationResult": {
                "AccessToken": "mock-access-token",
                "RefreshToken": "mock-refresh-token",
            },
            "ChallengeName": "SUCCESS",
        },
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.hive.config_flow.Auth.login",
            return_value={
                "ChallengeName": "SUCCESS",
                "AuthenticationResult": {
                    "RefreshToken": "mock-refresh-token",
                    "AccessToken": "mock-access-token",
                },
            },
        ),
        patch(
            "homeassistant.components.hive.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.hive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == USERNAME
    assert result2["data"] == {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
        "tokens": {
            "AuthenticationResult": {
                "AccessToken": "mock-access-token",
                "RefreshToken": "mock-refresh-token",
            },
            "ChallengeName": "SUCCESS",
        },
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_user_flow_2fa(hass: HomeAssistant) -> None:
    """Test user flow with 2FA."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        return_value={
            "ChallengeName": "SMS_MFA",
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == CONF_CODE
    assert result2["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.sms_2fa",
        return_value={
            "ChallengeName": "SUCCESS",
            "AuthenticationResult": {
                "RefreshToken": "mock-refresh-token",
                "AccessToken": "mock-access-token",
            },
        },
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CODE: MFA_CODE,
            },
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "configuration"
    assert result3["errors"] == {}

    with (
        patch(
            "homeassistant.components.hive.config_flow.Auth.device_registration",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hive.config_flow.Auth.get_device_data",
            return_value=[
                "mock-device-group-key",
                "mock-device-key",
                "mock-device-password",
            ],
        ),
        patch(
            "homeassistant.components.hive.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.hive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_NAME: DEVICE_NAME,
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == USERNAME
    assert result4["data"] == {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
        "tokens": {
            "AuthenticationResult": {
                "AccessToken": "mock-access-token",
                "RefreshToken": "mock-refresh-token",
            },
            "ChallengeName": "SUCCESS",
        },
        "device_data": [
            "mock-device-group-key",
            "mock-device-key",
            "mock-device-password",
        ],
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test the reauth flow."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USERNAME,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: INCORRECT_PASSWORD,
            "tokens": {
                "AccessToken": "mock-access-token",
                "RefreshToken": "mock-refresh-token",
            },
        },
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        side_effect=hive_exceptions.HiveInvalidPassword(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": mock_config.unique_id,
            },
            data=mock_config.data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_password"}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        return_value={
            "ChallengeName": "SUCCESS",
            "AuthenticationResult": {
                "RefreshToken": "mock-refresh-token",
                "AccessToken": "mock-access-token",
            },
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: UPDATED_PASSWORD,
            },
        )
    await hass.async_block_till_done()

    assert mock_config.data.get("username") == USERNAME
    assert mock_config.data.get("password") == UPDATED_PASSWORD
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauth_2fa_flow(hass: HomeAssistant) -> None:
    """Test the reauth flow."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USERNAME,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: INCORRECT_PASSWORD,
            "tokens": {
                "AccessToken": "mock-access-token",
                "RefreshToken": "mock-refresh-token",
            },
        },
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        side_effect=hive_exceptions.HiveInvalidPassword(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": mock_config.unique_id,
            },
            data=mock_config.data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_password"}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        return_value={
            "ChallengeName": "SMS_MFA",
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: UPDATED_PASSWORD,
            },
        )

    with (
        patch(
            "homeassistant.components.hive.config_flow.Auth.sms_2fa",
            return_value={
                "ChallengeName": "SUCCESS",
                "AuthenticationResult": {
                    "RefreshToken": "mock-refresh-token",
                    "AccessToken": "mock-access-token",
                },
            },
        ),
        patch(
            "homeassistant.components.hive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_CODE: MFA_CODE,
            },
        )
        await hass.async_block_till_done()

    assert mock_config.data.get("username") == USERNAME
    assert mock_config.data.get("password") == UPDATED_PASSWORD
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_option_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            "device_data": [
                "mock-device-group-key",
                "mock-device-key",
                "mock-device-password",
            ],
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        data=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SCAN_INTERVAL: UPDATED_SCAN_INTERVAL}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCAN_INTERVAL] == UPDATED_SCAN_INTERVAL


async def test_user_flow_2fa_send_new_code(hass: HomeAssistant) -> None:
    """Resend a 2FA code if it didn't arrive."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        return_value={
            "ChallengeName": "SMS_MFA",
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == CONF_CODE
    assert result2["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        return_value={
            "ChallengeName": "SMS_MFA",
        },
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {CONF_CODE: MFA_RESEND_CODE}
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == CONF_CODE
    assert result3["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.sms_2fa",
        return_value={
            "ChallengeName": "SUCCESS",
            "AuthenticationResult": {
                "RefreshToken": "mock-refresh-token",
                "AccessToken": "mock-access-token",
            },
        },
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CODE: MFA_CODE,
            },
        )

    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == "configuration"
    assert result4["errors"] == {}

    with (
        patch(
            "homeassistant.components.hive.config_flow.Auth.device_registration",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hive.config_flow.Auth.get_device_data",
            return_value=[
                "mock-device-group-key",
                "mock-device-key",
                "mock-device-password",
            ],
        ),
        patch(
            "homeassistant.components.hive.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.hive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"], {CONF_DEVICE_NAME: DEVICE_NAME}
        )
        await hass.async_block_till_done()

    assert result5["type"] is FlowResultType.CREATE_ENTRY
    assert result5["title"] == USERNAME
    assert result5["data"] == {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
        "tokens": {
            "AuthenticationResult": {
                "AccessToken": "mock-access-token",
                "RefreshToken": "mock-refresh-token",
            },
            "ChallengeName": "SUCCESS",
        },
        "device_data": [
            "mock-device-group-key",
            "mock-device-key",
            "mock-device-password",
        ],
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_abort_if_existing_entry(hass: HomeAssistant) -> None:
    """Check flow abort when an entry already exist."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USERNAME,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        options={CONF_SCAN_INTERVAL: SCAN_INTERVAL},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_invalid_username(hass: HomeAssistant) -> None:
    """Test user flow with invalid username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        side_effect=hive_exceptions.HiveInvalidUsername(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_username"}


async def test_user_flow_invalid_password(hass: HomeAssistant) -> None:
    """Test user flow with invalid password."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        side_effect=hive_exceptions.HiveInvalidPassword(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_password"}


async def test_user_flow_no_internet_connection(hass: HomeAssistant) -> None:
    """Test user flow with no internet connection."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        side_effect=hive_exceptions.HiveApiError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "no_internet_available"}


async def test_user_flow_2fa_no_internet_connection(hass: HomeAssistant) -> None:
    """Test user flow with no internet connection."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        return_value={
            "ChallengeName": "SMS_MFA",
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == CONF_CODE
    assert result2["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.sms_2fa",
        side_effect=hive_exceptions.HiveApiError(),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_CODE: MFA_CODE},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == CONF_CODE
    assert result3["errors"] == {"base": "no_internet_available"}


async def test_user_flow_2fa_invalid_code(hass: HomeAssistant) -> None:
    """Test user flow with 2FA."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        return_value={
            "ChallengeName": "SMS_MFA",
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == CONF_CODE
    assert result2["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.sms_2fa",
        side_effect=hive_exceptions.HiveInvalid2FACode(),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CODE: MFA_INVALID_CODE},
        )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == CONF_CODE
    assert result3["errors"] == {"base": "invalid_code"}


async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test user flow when unknown error occurs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        return_value={"ChallengeName": "FAILED", "InvalidAuthenticationResult": {}},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_user_flow_2fa_unknown_error(hass: HomeAssistant) -> None:
    """Test 2fa flow when unknown error occurs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hive.config_flow.Auth.login",
        return_value={
            "ChallengeName": "SMS_MFA",
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == CONF_CODE

    with patch(
        "homeassistant.components.hive.config_flow.Auth.sms_2fa",
        return_value={"ChallengeName": "FAILED", "InvalidAuthenticationResult": {}},
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_CODE: MFA_CODE},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "configuration"
    assert result3["errors"] == {}

    with (
        patch(
            "homeassistant.components.hive.config_flow.Auth.device_registration",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hive.config_flow.Auth.get_device_data",
            return_value=[
                "mock-device-group-key",
                "mock-device-key",
                "mock-device-password",
            ],
        ),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_NAME: DEVICE_NAME},
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == "configuration"
    assert result4["errors"] == {"base": "unknown"}
