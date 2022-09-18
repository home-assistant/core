"""Test the HMAC-based One Time Password (MFA) auth module."""
import asyncio
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.auth import auth_manager_from_config, models as auth_models
from homeassistant.auth.mfa_modules import auth_mfa_module_from_config
from homeassistant.components.notify import NOTIFY_SERVICE_SCHEMA

from tests.common import MockUser, async_mock_service

MOCK_CODE = "123456"
MOCK_CODE_2 = "654321"


async def test_validating_mfa(hass):
    """Test validating mfa code."""
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user("test-user", {"notify_service": "dummy"})

    with patch("pyotp.HOTP.verify", return_value=True):
        assert await notify_auth_module.async_validate("test-user", {"code": MOCK_CODE})


async def test_validating_mfa_invalid_code(hass):
    """Test validating an invalid mfa code."""
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user("test-user", {"notify_service": "dummy"})

    with patch("pyotp.HOTP.verify", return_value=False):
        assert (
            await notify_auth_module.async_validate("test-user", {"code": MOCK_CODE})
            is False
        )


async def test_validating_mfa_invalid_user(hass):
    """Test validating an mfa code with invalid user."""
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user("test-user", {"notify_service": "dummy"})

    assert (
        await notify_auth_module.async_validate("invalid-user", {"code": MOCK_CODE})
        is False
    )


async def test_validating_mfa_counter(hass):
    """Test counter will move only after generate code."""
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user(
        "test-user", {"counter": 0, "notify_service": "dummy"}
    )
    async_mock_service(hass, "notify", "dummy")

    assert notify_auth_module._user_settings
    notify_setting = list(notify_auth_module._user_settings.values())[0]
    init_count = notify_setting.counter
    assert init_count is not None

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        await notify_auth_module.async_initialize_login_mfa_step("test-user")

    notify_setting = list(notify_auth_module._user_settings.values())[0]
    after_generate_count = notify_setting.counter
    assert after_generate_count != init_count

    with patch("pyotp.HOTP.verify", return_value=True):
        assert await notify_auth_module.async_validate("test-user", {"code": MOCK_CODE})

    notify_setting = list(notify_auth_module._user_settings.values())[0]
    assert after_generate_count == notify_setting.counter

    with patch("pyotp.HOTP.verify", return_value=False):
        assert (
            await notify_auth_module.async_validate("test-user", {"code": MOCK_CODE})
            is False
        )

    notify_setting = list(notify_auth_module._user_settings.values())[0]
    assert after_generate_count == notify_setting.counter


async def test_setup_depose_user(hass):
    """Test set up and despose user."""
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user("test-user", {})
    assert len(notify_auth_module._user_settings) == 1
    await notify_auth_module.async_setup_user("test-user", {})
    assert len(notify_auth_module._user_settings) == 1

    await notify_auth_module.async_depose_user("test-user")
    assert len(notify_auth_module._user_settings) == 0

    await notify_auth_module.async_setup_user("test-user2", {"secret": "secret-code"})
    assert len(notify_auth_module._user_settings) == 1


async def test_login_flow_validates_mfa(hass):
    """Test login flow with mfa enabled."""
    hass.auth = await auth_manager_from_config(
        hass,
        [
            {
                "type": "insecure_example",
                "users": [{"username": "test-user", "password": "test-pass"}],
            }
        ],
        [{"type": "notify"}],
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

    notify_calls = async_mock_service(
        hass, "notify", "test-notify", NOTIFY_SERVICE_SCHEMA
    )

    await hass.auth.async_enable_user_mfa(
        user, "notify", {"notify_service": "test-notify"}
    )

    provider = hass.auth.auth_providers[0]

    result = await hass.auth.login_flow.async_init((provider.type, provider.id))
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await hass.auth.login_flow.async_configure(
        result["flow_id"], {"username": "incorrect-user", "password": "test-pass"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"

    result = await hass.auth.login_flow.async_configure(
        result["flow_id"], {"username": "test-user", "password": "incorrect-pass"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"username": "test-user", "password": "test-pass"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["data_schema"].schema.get("code") == str

    # wait service call finished
    await hass.async_block_till_done()

    assert len(notify_calls) == 1
    notify_call = notify_calls[0]
    assert notify_call.domain == "notify"
    assert notify_call.service == "test-notify"
    message = notify_call.data["message"]
    message.hass = hass
    assert MOCK_CODE in message.async_render()

    with patch("pyotp.HOTP.verify", return_value=False):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": "invalid-code"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"]["base"] == "invalid_code"

    # wait service call finished
    await hass.async_block_till_done()

    # would not send new code, allow user retry
    assert len(notify_calls) == 1

    # retry twice
    with patch("pyotp.HOTP.verify", return_value=False), patch(
        "pyotp.HOTP.at", return_value=MOCK_CODE_2
    ):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": "invalid-code"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"]["base"] == "invalid_code"

        # after the 3rd failure, flow abort
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": "invalid-code"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "too_many_retry"

    # wait service call finished
    await hass.async_block_till_done()

    # restart login
    result = await hass.auth.login_flow.async_init((provider.type, provider.id))
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"username": "test-user", "password": "test-pass"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["data_schema"].schema.get("code") == str

    # wait service call finished
    await hass.async_block_till_done()

    assert len(notify_calls) == 2
    notify_call = notify_calls[1]
    assert notify_call.domain == "notify"
    assert notify_call.service == "test-notify"
    message = notify_call.data["message"]
    message.hass = hass
    assert MOCK_CODE in message.async_render()

    with patch("pyotp.HOTP.verify", return_value=True):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": MOCK_CODE}
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"].id == "mock-id"


async def test_setup_user_notify_service(hass):
    """Test allow select notify service during mfa setup."""
    notify_calls = async_mock_service(hass, "notify", "test1", NOTIFY_SERVICE_SCHEMA)
    async_mock_service(hass, "notify", "test2", NOTIFY_SERVICE_SCHEMA)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})

    services = notify_auth_module.aync_get_available_notify_services()
    assert services == ["test1", "test2"]

    flow = await notify_auth_module.async_setup_flow("test-user")
    step = await flow.async_step_init()
    assert step["type"] == data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "init"
    schema = step["data_schema"]
    schema({"notify_service": "test2"})

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        step = await flow.async_step_init({"notify_service": "test1"})
        assert step["type"] == data_entry_flow.FlowResultType.FORM
        assert step["step_id"] == "setup"

    # wait service call finished
    await hass.async_block_till_done()

    assert len(notify_calls) == 1
    notify_call = notify_calls[0]
    assert notify_call.domain == "notify"
    assert notify_call.service == "test1"
    message = notify_call.data["message"]
    message.hass = hass
    assert MOCK_CODE in message.async_render()

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE_2):
        step = await flow.async_step_setup({"code": "invalid"})
        assert step["type"] == data_entry_flow.FlowResultType.FORM
        assert step["step_id"] == "setup"
        assert step["errors"]["base"] == "invalid_code"

    # wait service call finished
    await hass.async_block_till_done()

    assert len(notify_calls) == 2
    notify_call = notify_calls[1]
    assert notify_call.domain == "notify"
    assert notify_call.service == "test1"
    message = notify_call.data["message"]
    message.hass = hass
    assert MOCK_CODE_2 in message.async_render()

    with patch("pyotp.HOTP.verify", return_value=True):
        step = await flow.async_step_setup({"code": MOCK_CODE_2})
        assert step["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_include_exclude_config(hass):
    """Test allow include exclude config."""
    async_mock_service(hass, "notify", "include1", NOTIFY_SERVICE_SCHEMA)
    async_mock_service(hass, "notify", "include2", NOTIFY_SERVICE_SCHEMA)
    async_mock_service(hass, "notify", "exclude1", NOTIFY_SERVICE_SCHEMA)
    async_mock_service(hass, "notify", "exclude2", NOTIFY_SERVICE_SCHEMA)
    async_mock_service(hass, "other", "include3", NOTIFY_SERVICE_SCHEMA)
    async_mock_service(hass, "other", "exclude3", NOTIFY_SERVICE_SCHEMA)

    notify_auth_module = await auth_mfa_module_from_config(
        hass, {"type": "notify", "exclude": ["exclude1", "exclude2", "exclude3"]}
    )
    services = notify_auth_module.aync_get_available_notify_services()
    assert services == ["include1", "include2"]

    notify_auth_module = await auth_mfa_module_from_config(
        hass, {"type": "notify", "include": ["include1", "include2", "include3"]}
    )
    services = notify_auth_module.aync_get_available_notify_services()
    assert services == ["include1", "include2"]

    # exclude has high priority than include
    notify_auth_module = await auth_mfa_module_from_config(
        hass,
        {
            "type": "notify",
            "include": ["include1", "include2", "include3"],
            "exclude": ["exclude1", "exclude2", "include2"],
        },
    )
    services = notify_auth_module.aync_get_available_notify_services()
    assert services == ["include1"]


async def test_setup_user_no_notify_service(hass):
    """Test setup flow abort if there is no available notify service."""
    async_mock_service(hass, "notify", "test1", NOTIFY_SERVICE_SCHEMA)
    notify_auth_module = await auth_mfa_module_from_config(
        hass, {"type": "notify", "exclude": "test1"}
    )

    services = notify_auth_module.aync_get_available_notify_services()
    assert services == []

    flow = await notify_auth_module.async_setup_flow("test-user")
    step = await flow.async_step_init()
    assert step["type"] == data_entry_flow.FlowResultType.ABORT
    assert step["reason"] == "no_available_service"


async def test_not_raise_exception_when_service_not_exist(hass):
    """Test login flow will not raise exception when notify service error."""
    hass.auth = await auth_manager_from_config(
        hass,
        [
            {
                "type": "insecure_example",
                "users": [{"username": "test-user", "password": "test-pass"}],
            }
        ],
        [{"type": "notify"}],
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

    await hass.auth.async_enable_user_mfa(
        user, "notify", {"notify_service": "invalid-notify"}
    )

    provider = hass.auth.auth_providers[0]

    result = await hass.auth.login_flow.async_init((provider.type, provider.id))
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"username": "test-user", "password": "test-pass"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "unknown_error"

    # wait service call finished
    await hass.async_block_till_done()


async def test_race_condition_in_data_loading(hass):
    """Test race condition in the data loading."""
    counter = 0

    async def mock_load(_):
        """Mock homeassistant.helpers.storage.Store.async_load."""
        nonlocal counter
        counter += 1
        await asyncio.sleep(0)

    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    with patch("homeassistant.helpers.storage.Store.async_load", new=mock_load):
        task1 = notify_auth_module.async_validate("user", {"code": "value"})
        task2 = notify_auth_module.async_validate("user", {"code": "value"})
        results = await asyncio.gather(task1, task2, return_exceptions=True)
        assert counter == 1
        assert results[0] is False
        assert results[1] is False
