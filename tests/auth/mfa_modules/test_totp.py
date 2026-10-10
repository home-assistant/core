"""Test the Time-based One Time Password (MFA) auth module."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time
import pyotp

from homeassistant import data_entry_flow
from homeassistant.auth import auth_manager_from_config, models as auth_models
from homeassistant.auth.mfa_modules import auth_mfa_module_from_config
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockUser

MOCK_CODE = "123456"


async def test_validating_mfa(hass: HomeAssistant) -> None:
    """Test validating mfa code."""
    totp_auth_module = await auth_mfa_module_from_config(hass, {"type": "totp"})
    await totp_auth_module.async_setup_user("test-user", {})

    with patch("pyotp.TOTP.verify", return_value=True):
        assert await totp_auth_module.async_validate("test-user", {"code": MOCK_CODE})


async def test_validating_mfa_invalid_code(hass: HomeAssistant) -> None:
    """Test validating an invalid mfa code."""
    totp_auth_module = await auth_mfa_module_from_config(hass, {"type": "totp"})
    await totp_auth_module.async_setup_user("test-user", {})

    with patch("pyotp.TOTP.verify", return_value=False):
        assert (
            await totp_auth_module.async_validate("test-user", {"code": MOCK_CODE})
            is False
        )


async def test_validating_mfa_invalid_user(hass: HomeAssistant) -> None:
    """Test validating an mfa code with invalid user."""
    totp_auth_module = await auth_mfa_module_from_config(hass, {"type": "totp"})
    await totp_auth_module.async_setup_user("test-user", {})

    assert (
        await totp_auth_module.async_validate("invalid-user", {"code": MOCK_CODE})
        is False
    )


async def test_setup_depose_user(hass: HomeAssistant) -> None:
    """Test despose user."""
    totp_auth_module = await auth_mfa_module_from_config(hass, {"type": "totp"})
    result = await totp_auth_module.async_setup_user("test-user", {})
    assert len(totp_auth_module._users) == 1
    result2 = await totp_auth_module.async_setup_user("test-user", {})
    assert len(totp_auth_module._users) == 1
    assert result != result2

    await totp_auth_module.async_depose_user("test-user")
    assert len(totp_auth_module._users) == 0

    result = await totp_auth_module.async_setup_user(
        "test-user2", {"secret": "secret-code"}
    )
    assert result == "secret-code"
    assert len(totp_auth_module._users) == 1


async def test_login_flow_validates_mfa(hass: HomeAssistant) -> None:
    """Test login flow with mfa enabled."""
    hass.auth = await auth_manager_from_config(
        hass,
        [
            {
                "type": "insecure_example",
                "users": [{"username": "test-user", "password": "test-pass"}],
            }
        ],
        [{"type": "totp"}],
    )
    user = MockUser(
        id="mock-user", is_owner=False, is_active=False, name="Paulus"
    ).add_to_auth_manager(hass.auth)
    await hass.auth.async_link_user(
        user,
        auth_models.Credentials(
            id="mock-id",
            auth_provider_type="insecure_example",
            auth_provider_id=None,
            data={"username": "test-user"},
            is_new=False,
        ),
    )

    await hass.auth.async_enable_user_mfa(user, "totp", {})

    provider = hass.auth.auth_providers[0]

    result = await hass.auth.login_flow.async_init((provider.type, provider.id))
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.auth.login_flow.async_configure(
        result["flow_id"], {"username": "incorrect-user", "password": "test-pass"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"

    result = await hass.auth.login_flow.async_configure(
        result["flow_id"], {"username": "test-user", "password": "incorrect-pass"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"

    result = await hass.auth.login_flow.async_configure(
        result["flow_id"], {"username": "test-user", "password": "test-pass"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "mfa"
    assert result["data_schema"].schema.get("code") is str

    with patch("pyotp.TOTP.verify", return_value=False):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": "invalid-code"}
        )
        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"]["base"] == "invalid_code"

    with patch("pyotp.TOTP.verify", return_value=True):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": MOCK_CODE}
        )
        assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"].id == "mock-id"


async def test_setup_flow_accepts_code_with_clock_drift(hass: HomeAssistant) -> None:
    """Test setup flow tolerates the same clock drift as login validation."""
    totp_auth_module = await auth_mfa_module_from_config(hass, {"type": "totp"})
    user = MockUser(id="mock-user").add_to_auth_manager(hass.auth)

    with freeze_time(datetime(2024, 1, 1, 0, 0, 5)):
        flow = await totp_auth_module.async_setup_flow(user.id)
        flow.hass = hass
        await flow.async_step_init()

        drifted_code = pyotp.TOTP(flow._ota_secret).at(
            dt_util.naive_now() - timedelta(seconds=25)
        )
        result = await flow.async_step_init({"code": drifted_code})

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_race_condition_in_data_loading(hass: HomeAssistant) -> None:
    """Test race condition in the data loading."""
    counter = 0

    async def mock_load(_):
        """Mock of homeassistant.helpers.storage.Store.async_load."""
        nonlocal counter
        counter += 1
        await asyncio.sleep(0)

    totp_auth_module = await auth_mfa_module_from_config(hass, {"type": "totp"})
    with patch("homeassistant.helpers.storage.Store.async_load", new=mock_load):
        task1 = totp_auth_module.async_validate("user", {"code": "value"})
        task2 = totp_auth_module.async_validate("user", {"code": "value"})
        results = await asyncio.gather(task1, task2, return_exceptions=True)
        assert counter == 1
        assert results[0] is False
        assert results[1] is False
