"""Test the HMAC-based One Time Password (MFA) auth module."""

import asyncio
from typing import Any
from unittest.mock import patch

from probatio import to_field_list
import pytest

from homeassistant import data_entry_flow
from homeassistant.auth import auth_manager_from_config, models as auth_models
from homeassistant.auth.mfa_modules import auth_mfa_module_from_config
from homeassistant.components.notify import NOTIFY_SERVICE_SCHEMA
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from tests.common import MockUser, async_mock_service

MOCK_CODE = "123456"
MOCK_CODE_2 = "654321"
NOTIFY_ENTITY_ID = "notify.phone"
NOTIFY_ENTITY_ID_2 = "notify.tablet"


async def test_validating_mfa(hass: HomeAssistant) -> None:
    """Test validating mfa code."""
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user("test-user", {"notify_service": "dummy"})

    with patch("pyotp.HOTP.verify", return_value=True):
        assert await notify_auth_module.async_validate("test-user", {"code": MOCK_CODE})


async def test_validating_mfa_invalid_code(hass: HomeAssistant) -> None:
    """Test validating an invalid mfa code."""
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user("test-user", {"notify_service": "dummy"})

    with patch("pyotp.HOTP.verify", return_value=False):
        assert (
            await notify_auth_module.async_validate("test-user", {"code": MOCK_CODE})
            is False
        )


async def test_validating_mfa_invalid_user(hass: HomeAssistant) -> None:
    """Test validating an mfa code with invalid user."""
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user("test-user", {"notify_service": "dummy"})

    assert (
        await notify_auth_module.async_validate("invalid-user", {"code": MOCK_CODE})
        is False
    )


async def test_validating_mfa_counter(hass: HomeAssistant) -> None:
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


async def test_setup_depose_user(hass: HomeAssistant) -> None:
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

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"username": "test-user", "password": "test-pass"}
        )
        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["data_schema"].schema.get("code") is str

    # wait service call finished
    await hass.async_block_till_done()

    assert len(notify_calls) == 1
    notify_call = notify_calls[0]
    assert notify_call.domain == "notify"
    assert notify_call.service == "test-notify"
    message = notify_call.data["message"]
    assert MOCK_CODE in message

    with patch("pyotp.HOTP.verify", return_value=False):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": "invalid-code"}
        )
        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"]["base"] == "invalid_code"

    # wait service call finished
    await hass.async_block_till_done()

    # would not send new code, allow user retry
    assert len(notify_calls) == 1

    # retry twice
    with (
        patch("pyotp.HOTP.verify", return_value=False),
        patch("pyotp.HOTP.at", return_value=MOCK_CODE_2),
    ):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": "invalid-code"}
        )
        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"]["base"] == "invalid_code"

        # after the 3rd failure, flow abort
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": "invalid-code"}
        )
        assert result["type"] is data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "too_many_retry"

    # wait service call finished
    await hass.async_block_till_done()

    # restart login
    result = await hass.auth.login_flow.async_init((provider.type, provider.id))
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"username": "test-user", "password": "test-pass"}
        )
        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["data_schema"].schema.get("code") is str

    # wait service call finished
    await hass.async_block_till_done()

    assert len(notify_calls) == 2
    notify_call = notify_calls[1]
    assert notify_call.domain == "notify"
    assert notify_call.service == "test-notify"
    message = notify_call.data["message"]
    assert MOCK_CODE in message

    with patch("pyotp.HOTP.verify", return_value=True):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"code": MOCK_CODE}
        )
        assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"].id == "mock-id"


async def test_setup_user_notify_service(hass: HomeAssistant) -> None:
    """Test allow select notify service during mfa setup."""
    notify_calls = async_mock_service(hass, "notify", "test1", NOTIFY_SERVICE_SCHEMA)
    async_mock_service(hass, "notify", "test2", NOTIFY_SERVICE_SCHEMA)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})

    services = notify_auth_module.aync_get_available_notify_services()
    assert services == ["test1", "test2"]

    flow = await notify_auth_module.async_setup_flow("test-user")
    step = await flow.async_step_init()
    assert step["type"] is data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "init"
    schema = step["data_schema"]
    schema({"notify_service": "test2"})
    # ensure the schema can be serialized
    assert to_field_list(schema) == [
        {
            "name": "notify_service",
            "options": [
                (
                    "test1",
                    "test1",
                ),
                (
                    "test2",
                    "test2",
                ),
            ],
            "required": True,
            "type": "select",
        },
        {
            "name": "target",
            "optional": True,
            "required": False,
            "type": "string",
        },
    ]

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        step = await flow.async_step_init({"notify_service": "test1"})
        assert step["type"] is data_entry_flow.FlowResultType.FORM
        assert step["step_id"] == "setup"

    # wait service call finished
    await hass.async_block_till_done()

    assert len(notify_calls) == 1
    notify_call = notify_calls[0]
    assert notify_call.domain == "notify"
    assert notify_call.service == "test1"
    message = notify_call.data["message"]
    assert MOCK_CODE in message

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
    assert MOCK_CODE_2 in message

    with patch("pyotp.HOTP.verify", return_value=True):
        step = await flow.async_step_setup({"code": MOCK_CODE_2})
        assert step["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_include_exclude_config(hass: HomeAssistant) -> None:
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


async def test_setup_user_no_notify_service(hass: HomeAssistant) -> None:
    """Test setup flow abort if there is no available notify service."""
    async_mock_service(hass, "notify", "test1", NOTIFY_SERVICE_SCHEMA)
    notify_auth_module = await auth_mfa_module_from_config(
        hass, {"type": "notify", "exclude": "test1"}
    )

    services = notify_auth_module.aync_get_available_notify_services()
    assert services == []

    flow = await notify_auth_module.async_setup_flow("test-user")
    step = await flow.async_step_init()
    assert step["type"] is data_entry_flow.FlowResultType.ABORT
    assert step["reason"] == "no_available_service"


async def test_not_raise_exception_when_service_not_exist(hass: HomeAssistant) -> None:
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
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        result = await hass.auth.login_flow.async_configure(
            result["flow_id"], {"username": "test-user", "password": "test-pass"}
        )
        assert result["type"] is data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "unknown_error"

    # wait service call finished
    await hass.async_block_till_done()


async def test_race_condition_in_data_loading(hass: HomeAssistant) -> None:
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


async def test_setup_user_notify_entities(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test allow select notify entities during mfa setup."""
    async_mock_service(hass, "notify", "test1", NOTIFY_SERVICE_SCHEMA)
    notify_calls = async_mock_service(hass, "notify", "send_message")
    hass.states.async_set(NOTIFY_ENTITY_ID, STATE_UNKNOWN)
    hass.states.async_set(NOTIFY_ENTITY_ID_2, STATE_UNKNOWN)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})

    assert notify_auth_module.aync_get_available_notify_services() == ["test1"]
    assert notify_auth_module.async_get_available_notify_entities() == [
        NOTIFY_ENTITY_ID,
        NOTIFY_ENTITY_ID_2,
    ]

    flow = await notify_auth_module.async_setup_flow("test-user")
    step = await flow.async_step_init()
    assert step["type"] is data_entry_flow.FlowResultType.FORM
    assert to_field_list(
        step["data_schema"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "entity_ids",
            "optional": True,
            "required": False,
            "selector": {
                "entity": {
                    "domain": ["notify"],
                    "include_entities": [NOTIFY_ENTITY_ID, NOTIFY_ENTITY_ID_2],
                    "multiple": True,
                    "reorder": False,
                }
            },
        },
        {
            "name": "notify_service",
            "options": [("test1", "test1")],
            "optional": True,
            "required": False,
            "type": "select",
        },
        {
            "name": "target",
            "optional": True,
            "required": False,
            "type": "string",
        },
    ]

    entity_ids = [NOTIFY_ENTITY_ID, NOTIFY_ENTITY_ID_2]
    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        step = await flow.async_step_init(
            {"entity_ids": entity_ids, "target": "ignored"}
        )
    assert step["type"] is data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "setup"
    assert step["description_placeholders"] == {
        "notify_target": f"{NOTIFY_ENTITY_ID}, {NOTIFY_ENTITY_ID_2}"
    }

    assert [call.data["entity_id"] for call in notify_calls] == entity_ids
    assert all(MOCK_CODE in call.data["message"] for call in notify_calls)

    with patch("pyotp.HOTP.verify", return_value=True):
        step = await flow.async_step_setup({"code": MOCK_CODE})
    assert step["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY

    assert hass_storage["auth_module.notify"]["data"]["users"] == {
        "test-user": {
            "notify_service": None,
            "target": None,
            "entity_ids": entity_ids,
        }
    }

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE_2):
        await notify_auth_module.async_initialize_login_mfa_step("test-user")

    assert [call.data["entity_id"] for call in notify_calls[2:]] == entity_ids
    assert all(MOCK_CODE_2 in call.data["message"] for call in notify_calls[2:])


async def test_entity_ids_not_stored_for_notify_service(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test entity_ids is not stored when a notify service is used."""
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user(
        "test-user", {"notify_service": "dummy", "target": "target"}
    )

    assert hass_storage["auth_module.notify"]["data"]["users"] == {
        "test-user": {"notify_service": "dummy", "target": "target"}
    }


async def test_include_exclude_notify_entities(hass: HomeAssistant) -> None:
    """Test include and exclude config apply to notify entities."""
    for entity_id in ("notify.include1", "notify.include2", "notify.exclude1"):
        hass.states.async_set(entity_id, STATE_UNKNOWN)

    notify_auth_module = await auth_mfa_module_from_config(
        hass,
        {
            "type": "notify",
            "include": ["notify.include1", "notify.exclude1"],
            "exclude": ["notify.exclude1"],
        },
    )
    assert notify_auth_module.async_get_available_notify_entities() == [
        "notify.include1"
    ]


async def test_setup_user_only_notify_entities(hass: HomeAssistant) -> None:
    """Test setup flow only shows the entity field without notify services."""
    hass.states.async_set(NOTIFY_ENTITY_ID, STATE_UNKNOWN)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})

    flow = await notify_auth_module.async_setup_flow("test-user")
    step = await flow.async_step_init()
    assert step["type"] is data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "init"
    assert to_field_list(
        step["data_schema"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "entity_ids",
            "required": True,
            "selector": {
                "entity": {
                    "domain": ["notify"],
                    "include_entities": [NOTIFY_ENTITY_ID],
                    "multiple": True,
                    "reorder": False,
                }
            },
        },
    ]


@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param({}, id="neither"),
        pytest.param({"entity_ids": []}, id="no_entities"),
    ],
)
async def test_setup_user_select_service_or_entities(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> None:
    """Test setup flow requires a notify service or notify entities."""
    async_mock_service(hass, "notify", "test1", NOTIFY_SERVICE_SCHEMA)
    hass.states.async_set(NOTIFY_ENTITY_ID, STATE_UNKNOWN)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})

    flow = await notify_auth_module.async_setup_flow("test-user")
    step = await flow.async_step_init(user_input)
    assert step["type"] is data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "init"
    assert step["errors"] == {"base": "select_service_or_entity"}


async def test_notify_entities_skip_unavailable(hass: HomeAssistant) -> None:
    """Test the code is only sent to notify entities that are available."""
    notify_calls = async_mock_service(hass, "notify", "send_message")
    hass.states.async_set(NOTIFY_ENTITY_ID, STATE_UNKNOWN)
    hass.states.async_set(NOTIFY_ENTITY_ID_2, STATE_UNAVAILABLE)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user(
        "test-user",
        {"entity_ids": [NOTIFY_ENTITY_ID, NOTIFY_ENTITY_ID_2, "notify.missing"]},
    )

    await notify_auth_module.async_initialize_login_mfa_step("test-user")

    assert len(notify_calls) == 1
    assert notify_calls[0].data["entity_id"] == NOTIFY_ENTITY_ID


async def test_notify_entities_not_available(hass: HomeAssistant) -> None:
    """Test sending raises when no notify entity is available."""
    notify_calls = async_mock_service(hass, "notify", "send_message")
    hass.states.async_set(NOTIFY_ENTITY_ID, STATE_UNAVAILABLE)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user(
        "test-user", {"entity_ids": [NOTIFY_ENTITY_ID, "notify.missing"]}
    )

    with pytest.raises(HomeAssistantError):
        await notify_auth_module.async_initialize_login_mfa_step("test-user")

    assert notify_calls == []


async def test_setup_user_notify_entities_failed(hass: HomeAssistant) -> None:
    """Test setup flow aborts when the notify entities become unavailable."""
    async_mock_service(hass, "notify", "send_message")
    hass.states.async_set(NOTIFY_ENTITY_ID, STATE_UNKNOWN)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})

    flow = await notify_auth_module.async_setup_flow("test-user")
    hass.states.async_set(NOTIFY_ENTITY_ID, STATE_UNAVAILABLE)

    step = await flow.async_step_init({"entity_ids": [NOTIFY_ENTITY_ID]})
    assert step["type"] is data_entry_flow.FlowResultType.ABORT
    assert step["reason"] == "notify_failed"


async def test_setup_user_notify_service_and_entities(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test the code is sent to both the notify service and notify entities."""
    service_calls = async_mock_service(hass, "notify", "test1", NOTIFY_SERVICE_SCHEMA)
    entity_calls = async_mock_service(hass, "notify", "send_message")
    hass.states.async_set(NOTIFY_ENTITY_ID, STATE_UNKNOWN)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})

    flow = await notify_auth_module.async_setup_flow("test-user")
    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        step = await flow.async_step_init(
            {
                "notify_service": "test1",
                "target": "target",
                "entity_ids": [NOTIFY_ENTITY_ID],
            }
        )
    assert step["type"] is data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "setup"
    assert step["description_placeholders"] == {
        "notify_target": f"{NOTIFY_ENTITY_ID}, notify.test1"
    }

    # wait service call finished
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["target"] == ["target"]
    assert MOCK_CODE in service_calls[0].data["message"]
    assert len(entity_calls) == 1
    assert entity_calls[0].data["entity_id"] == NOTIFY_ENTITY_ID
    assert MOCK_CODE in entity_calls[0].data["message"]

    with patch("pyotp.HOTP.verify", return_value=True):
        step = await flow.async_step_setup({"code": MOCK_CODE})
    assert step["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY

    assert hass_storage["auth_module.notify"]["data"]["users"] == {
        "test-user": {
            "notify_service": "test1",
            "target": "target",
            "entity_ids": [NOTIFY_ENTITY_ID],
        }
    }


@pytest.mark.parametrize(
    (
        "notify_service",
        "entity_state",
        "expected_service_calls",
        "expected_entity_calls",
    ),
    [
        pytest.param("test1", STATE_UNAVAILABLE, 1, 0, id="entities_unavailable"),
        pytest.param("missing", STATE_UNKNOWN, 0, 1, id="service_missing"),
    ],
)
async def test_send_code_partial_failure(
    hass: HomeAssistant,
    notify_service: str,
    entity_state: str,
    expected_service_calls: int,
    expected_entity_calls: int,
) -> None:
    """Test the code is still sent when only some destinations fail."""
    service_calls = async_mock_service(hass, "notify", "test1", NOTIFY_SERVICE_SCHEMA)
    entity_calls = async_mock_service(hass, "notify", "send_message")
    hass.states.async_set(NOTIFY_ENTITY_ID, entity_state)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})
    await notify_auth_module.async_setup_user(
        "test-user",
        {
            "notify_service": notify_service,
            "entity_ids": [NOTIFY_ENTITY_ID],
        },
    )

    await notify_auth_module.async_initialize_login_mfa_step("test-user")
    await hass.async_block_till_done()

    assert len(service_calls) == expected_service_calls
    assert len(entity_calls) == expected_entity_calls


async def test_existing_send_message_service_setup(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test a stored user set up with the send_message service keeps working."""
    hass_storage["auth_module.notify"] = {
        "version": 1,
        "key": "auth_module.notify",
        "data": {
            "users": {"test-user": {"notify_service": "send_message", "target": None}}
        },
    }
    notify_calls = async_mock_service(hass, "notify", "send_message")
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})

    assert notify_auth_module.aync_get_available_notify_services() == []
    assert await notify_auth_module.async_is_user_setup("test-user")

    with patch("pyotp.HOTP.at", return_value=MOCK_CODE):
        await notify_auth_module.async_initialize_login_mfa_step("test-user")
    await hass.async_block_till_done()

    assert len(notify_calls) == 1
    assert MOCK_CODE in notify_calls[0].data["message"]


async def test_setup_user_notify_entities_partial_failure(
    hass: HomeAssistant,
) -> None:
    """Test the setup step only lists the destinations the code was sent to."""

    async def send_message(call: ServiceCall) -> None:
        if call.data["entity_id"] == NOTIFY_ENTITY_ID_2:
            raise HomeAssistantError("Failed to send")

    hass.services.async_register("notify", "send_message", send_message)
    hass.states.async_set(NOTIFY_ENTITY_ID, STATE_UNKNOWN)
    hass.states.async_set(NOTIFY_ENTITY_ID_2, STATE_UNKNOWN)
    notify_auth_module = await auth_mfa_module_from_config(hass, {"type": "notify"})

    flow = await notify_auth_module.async_setup_flow("test-user")
    step = await flow.async_step_init(
        {"entity_ids": [NOTIFY_ENTITY_ID, NOTIFY_ENTITY_ID_2]}
    )
    assert step["type"] is data_entry_flow.FlowResultType.FORM
    assert step["step_id"] == "setup"
    assert step["description_placeholders"] == {"notify_target": NOTIFY_ENTITY_ID}
