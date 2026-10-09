"""Tests for the mfa setup flow."""

from unittest.mock import patch

from homeassistant.auth import auth_manager_from_config
from homeassistant.components.auth import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import (
    CLIENT_ID,
    MockUser,
    async_mock_service,
    ensure_auth_manager_loaded,
)
from tests.typing import WebSocketGenerator


async def test_ws_setup_depose_mfa(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test set up mfa module for current user."""
    hass.auth = await auth_manager_from_config(
        hass,
        provider_configs=[
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    }
                ],
            }
        ],
        module_configs=[
            {
                "type": "insecure_example",
                "id": "example_module",
                "data": [{"user_id": "mock-user", "pin": "123456"}],
            }
        ],
    )
    ensure_auth_manager_loaded(hass.auth)
    await async_setup_component(hass, DOMAIN, {"http": {}})

    user = MockUser(id="mock-user").add_to_hass(hass)
    cred = await hass.auth.auth_providers[0].async_get_or_create_credentials(
        {"username": "test-user"}
    )
    await hass.auth.async_link_user(user, cred)
    refresh_token = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)

    await client.send_json(
        {
            "id": 10,
            "type": "auth/setup_mfa",
            "mfa_module_id": "invalid_module",
        }
    )

    result = await client.receive_json()
    assert result["id"] == 10
    assert result["success"] is False
    assert result["error"]["code"] == "no_module"

    await client.send_json(
        {
            "id": 11,
            "type": "auth/setup_mfa",
            "mfa_module_id": "example_module",
        }
    )

    result = await client.receive_json()
    assert result["id"] == 11
    assert result["success"]

    flow = result["result"]
    # Cannot use identity `is` check here as the value is parsed from JSON
    assert flow["type"] == FlowResultType.FORM.value
    assert flow["handler"] == "example_module"
    assert flow["step_id"] == "init"
    assert flow["data_schema"][0] == {"type": "string", "name": "pin", "required": True}

    await client.send_json(
        {
            "id": 12,
            "type": "auth/setup_mfa",
            "flow_id": flow["flow_id"],
            "user_input": {"pin": "654321"},
        }
    )

    result = await client.receive_json()
    assert result["id"] == 12
    assert result["success"]

    flow = result["result"]
    # Cannot use identity `is` check here as the value is parsed from JSON
    assert flow["type"] == FlowResultType.CREATE_ENTRY.value
    assert flow["handler"] == "example_module"
    assert flow["data"]["result"] is None

    await client.send_json(
        {
            "id": 13,
            "type": "auth/depose_mfa",
            "mfa_module_id": "invalid_id",
        }
    )

    result = await client.receive_json()
    assert result["id"] == 13
    assert result["success"] is False
    assert result["error"]["code"] == "disable_failed"

    await client.send_json(
        {
            "id": 14,
            "type": "auth/depose_mfa",
            "mfa_module_id": "example_module",
        }
    )

    result = await client.receive_json()
    assert result["id"] == 14
    assert result["success"]
    assert result["result"] == "done"


async def test_ws_setup_mfa_selector(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test mfa setup flow serializes and validates selectors."""
    hass.auth = await auth_manager_from_config(
        hass,
        provider_configs=[{"type": "insecure_example", "users": []}],
        module_configs=[{"type": "notify"}],
    )
    ensure_auth_manager_loaded(hass.auth)
    await async_setup_component(hass, DOMAIN, {"http": {}})
    notify_calls = async_mock_service(hass, "notify", "send_message")
    hass.states.async_set("notify.phone", STATE_UNKNOWN)

    user = MockUser(id="mock-user").add_to_hass(hass)
    refresh_token = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)

    await client.send_json(
        {"id": 10, "type": "auth/setup_mfa", "mfa_module_id": "notify"}
    )

    result = await client.receive_json()
    assert result["success"]
    flow = result["result"]
    assert flow["step_id"] == "init"
    assert flow["data_schema"] == [
        {
            "name": "entity_ids",
            "required": True,
            "selector": {
                "entity": {
                    "domain": ["notify"],
                    "include_entities": ["notify.phone"],
                    "multiple": True,
                    "reorder": False,
                }
            },
        },
    ]

    with patch("pyotp.HOTP.at", return_value="123456"):
        await client.send_json(
            {
                "id": 11,
                "type": "auth/setup_mfa",
                "flow_id": flow["flow_id"],
                "user_input": {"entity_ids": ["notify.phone"]},
            }
        )
        result = await client.receive_json()

    assert result["success"]
    assert result["result"]["step_id"] == "setup"
    assert len(notify_calls) == 1
    assert notify_calls[0].data["entity_id"] == ["notify.phone"]
