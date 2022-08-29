"""Tests for the mfa setup flow."""
from homeassistant import data_entry_flow
from homeassistant.auth import auth_manager_from_config
from homeassistant.components.auth import mfa_setup_flow
from homeassistant.setup import async_setup_component

from tests.common import CLIENT_ID, MockUser, ensure_auth_manager_loaded


async def test_ws_setup_depose_mfa(hass, hass_ws_client):
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
    await async_setup_component(hass, "auth", {"http": {}})

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
            "type": mfa_setup_flow.WS_TYPE_SETUP_MFA,
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
            "type": mfa_setup_flow.WS_TYPE_SETUP_MFA,
            "mfa_module_id": "example_module",
        }
    )

    result = await client.receive_json()
    assert result["id"] == 11
    assert result["success"]

    flow = result["result"]
    assert flow["type"] == data_entry_flow.FlowResultType.FORM
    assert flow["handler"] == "example_module"
    assert flow["step_id"] == "init"
    assert flow["data_schema"][0] == {"type": "string", "name": "pin", "required": True}

    await client.send_json(
        {
            "id": 12,
            "type": mfa_setup_flow.WS_TYPE_SETUP_MFA,
            "flow_id": flow["flow_id"],
            "user_input": {"pin": "654321"},
        }
    )

    result = await client.receive_json()
    assert result["id"] == 12
    assert result["success"]

    flow = result["result"]
    assert flow["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert flow["handler"] == "example_module"
    assert flow["data"]["result"] is None

    await client.send_json(
        {
            "id": 13,
            "type": mfa_setup_flow.WS_TYPE_DEPOSE_MFA,
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
            "type": mfa_setup_flow.WS_TYPE_DEPOSE_MFA,
            "mfa_module_id": "example_module",
        }
    )

    result = await client.receive_json()
    assert result["id"] == 14
    assert result["success"]
    assert result["result"] == "done"
