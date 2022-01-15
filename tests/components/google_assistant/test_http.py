"""Test Google http services."""
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from unittest.mock import ANY, patch

from homeassistant.components.google_assistant import GOOGLE_ASSISTANT_SCHEMA
from homeassistant.components.google_assistant.const import (
    DOMAIN,
    EVENT_COMMAND_RECEIVED,
    HOMEGRAPH_TOKEN_URL,
    REPORT_STATE_BASE_URL,
    STORE_AGENT_USER_IDS,
    STORE_GOOGLE_LOCAL_WEBHOOK_ID,
)
from homeassistant.components.google_assistant.http import (
    GoogleConfig,
    _get_homegraph_jwt,
    _get_homegraph_token,
)
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.core import State
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events, async_mock_service

DUMMY_CONFIG = GOOGLE_ASSISTANT_SCHEMA(
    {
        "project_id": "1234",
        "service_account": {
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAKYscIlwm7soDsHAz6L6YvUkCvkrX19rS6yeYOmovvhoK5WeYGWUsd8V72zmsyHB7XO94YgJVjvxfzn5K8bLePjFzwoSJjZvhBJ/ZQ05d8VmbvgyWUoPdG9oEa4fZ/lCYrXoaFdTot2xcJvrb/ZuiRl4s4eZpNeFYvVK/Am7UeFPAgMBAAECgYAUetOfzLYUudofvPCaKHu7tKZ5kQPfEa0w6BAPnBF1Mfl1JiDBRDMryFtKs6AOIAVwx00dY/Ex0BCbB3+Cr58H7t4NaPTJxCpmR09pK7o17B7xAdQv8+SynFNud9/5vQ5AEXMOLNwKiU7wpXT6Z7ZIibUBOR7ewsWgsHCDpN1iqQJBAOMODPTPSiQMwRAUHIc6GPleFSJnIz2PAoG3JOG9KFAL6RtIc19lob2ZXdbQdzKtjSkWo+O5W20WDNAl1k32h6MCQQC7W4ZCIY67mPbL6CxXfHjpSGF4Dr9VWJ7ZrKHr6XUoOIcEvsn/pHvWonjMdy93rQMSfOE8BKd/I1+GHRmNVgplAkAnSo4paxmsZVyfeKt7Jy2dMY+8tVZe17maUuQaAE7Sk00SgJYegwrbMYgQnWCTL39HBfj0dmYA2Zj8CCAuu6O7AkEAryFiYjaUAO9+4iNoL27+ZrFtypeeadyov7gKs0ZKaQpNyzW8A+Zwi7TbTeSqzic/E+z/bOa82q7p/6b7141xsQJBANCAcIwMcVb6KVCHlQbOtKspo5Eh4ZQi8bGl+IcwbQ6JSxeTx915IfAldgbuU047wOB04dYCFB2yLDiUGVXTifU=\n-----END PRIVATE KEY-----\n",
            "client_email": "dummy@dummy.iam.gserviceaccount.com",
        },
    }
)
MOCK_TOKEN = {"access_token": "dummtoken", "expires_in": 3600}
MOCK_JSON = {"devices": {}}
MOCK_URL = "https://dummy"
MOCK_HEADER = {
    "Authorization": f"Bearer {MOCK_TOKEN['access_token']}",
    "X-GFE-SSL": "yes",
}


async def test_get_jwt(hass):
    """Test signing of key."""

    jwt = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJkdW1teUBkdW1teS5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsInNjb3BlIjoiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vYXV0aC9ob21lZ3JhcGgiLCJhdWQiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20vby9vYXV0aDIvdG9rZW4iLCJpYXQiOjE1NzEwMTEyMDAsImV4cCI6MTU3MTAxNDgwMH0.gG06SmY-zSvFwSrdFfqIdC6AnC22rwz-d2F2UDeWbywjdmFL_1zceL-OOLBwjD8MJr6nR0kmN_Osu7ml9-EzzZjJqsRUxMjGn2G8nSYHbv16R4FYIp62Ibvt6Jj_wdFobEPoy_5OJ28P5Hdu0giGMlFBJMy0Tc6MgEDZA-cwOBw"
    res = _get_homegraph_jwt(
        datetime(2019, 10, 14, tzinfo=timezone.utc),
        DUMMY_CONFIG["service_account"]["client_email"],
        DUMMY_CONFIG["service_account"]["private_key"],
    )
    assert res == jwt


async def test_get_access_token(hass, aioclient_mock):
    """Test the function to get access token."""
    jwt = "dummyjwt"

    aioclient_mock.post(
        HOMEGRAPH_TOKEN_URL,
        status=HTTPStatus.OK,
        json={"access_token": "1234", "expires_in": 3600},
    )

    await _get_homegraph_token(hass, jwt)
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][3] == {
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


async def test_update_access_token(hass):
    """Test the function to update access token when expired."""
    jwt = "dummyjwt"

    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()

    base_time = datetime(2019, 10, 14, tzinfo=timezone.utc)
    with patch(
        "homeassistant.components.google_assistant.http._get_homegraph_token"
    ) as mock_get_token, patch(
        "homeassistant.components.google_assistant.http._get_homegraph_jwt"
    ) as mock_get_jwt, patch(
        "homeassistant.core.dt_util.utcnow"
    ) as mock_utcnow:
        mock_utcnow.return_value = base_time
        mock_get_jwt.return_value = jwt
        mock_get_token.return_value = MOCK_TOKEN

        await config._async_update_token()
        mock_get_token.assert_called_once()

        mock_get_token.reset_mock()

        mock_utcnow.return_value = base_time + timedelta(seconds=3600)
        await config._async_update_token()
        mock_get_token.assert_not_called()

        mock_get_token.reset_mock()

        mock_utcnow.return_value = base_time + timedelta(seconds=3601)
        await config._async_update_token()
        mock_get_token.assert_called_once()


async def test_call_homegraph_api(hass, aioclient_mock, hass_storage, caplog):
    """Test the function to call the homegraph api."""
    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()

    with patch(
        "homeassistant.components.google_assistant.http._get_homegraph_token"
    ) as mock_get_token:
        mock_get_token.return_value = MOCK_TOKEN

        aioclient_mock.post(MOCK_URL, status=HTTPStatus.OK, json={})

        res = await config.async_call_homegraph_api(MOCK_URL, MOCK_JSON)
        assert res == HTTPStatus.OK

        assert mock_get_token.call_count == 1
        assert aioclient_mock.call_count == 1

        call = aioclient_mock.mock_calls[0]
        assert call[2] == MOCK_JSON
        assert call[3] == MOCK_HEADER


async def test_call_homegraph_api_retry(hass, aioclient_mock, hass_storage):
    """Test the that the calls get retried with new token on 401."""
    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()

    with patch(
        "homeassistant.components.google_assistant.http._get_homegraph_token"
    ) as mock_get_token:
        mock_get_token.return_value = MOCK_TOKEN

        aioclient_mock.post(MOCK_URL, status=HTTPStatus.UNAUTHORIZED, json={})

        await config.async_call_homegraph_api(MOCK_URL, MOCK_JSON)

        assert mock_get_token.call_count == 2
        assert aioclient_mock.call_count == 2

        call = aioclient_mock.mock_calls[0]
        assert call[2] == MOCK_JSON
        assert call[3] == MOCK_HEADER
        call = aioclient_mock.mock_calls[1]
        assert call[2] == MOCK_JSON
        assert call[3] == MOCK_HEADER


async def test_report_state(hass, aioclient_mock, hass_storage):
    """Test the report state function."""
    agent_user_id = "user"
    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()

    await config.async_connect_agent_user(agent_user_id)
    message = {"devices": {}}

    with patch.object(config, "async_call_homegraph_api"):
        # Wait for google_assistant.helpers.async_initialize.sync_google to be called
        await hass.async_block_till_done()

    with patch.object(config, "async_call_homegraph_api") as mock_call:
        await config.async_report_state(message, agent_user_id)
        mock_call.assert_called_once_with(
            REPORT_STATE_BASE_URL,
            {"requestId": ANY, "agentUserId": agent_user_id, "payload": message},
        )


async def test_google_config_local_fulfillment(hass, aioclient_mock, hass_storage):
    """Test the google config for local fulfillment."""
    agent_user_id = "user"
    local_webhook_id = "webhook"

    hass_storage["google_assistant"] = {
        "version": 1,
        "minor_version": 1,
        "key": "google_assistant",
        "data": {
            "agent_user_ids": {
                agent_user_id: {
                    "local_webhook_id": local_webhook_id,
                }
            },
        },
    }

    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()

    with patch.object(config, "async_call_homegraph_api"):
        # Wait for google_assistant.helpers.async_initialize.sync_google to be called
        await hass.async_block_till_done()

    assert config.get_local_webhook_id(agent_user_id) == local_webhook_id
    assert config.get_local_agent_user_id(local_webhook_id) == agent_user_id
    assert config.get_local_agent_user_id("INCORRECT") is None


async def test_secure_device_pin_config(hass):
    """Test the setting of the secure device pin configuration."""
    secure_pin = "TEST"
    secure_config = GOOGLE_ASSISTANT_SCHEMA(
        {
            "project_id": "1234",
            "service_account": {
                "private_key": "-----BEGIN PRIVATE KEY-----\nMIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAKYscIlwm7soDsHAz6L6YvUkCvkrX19rS6yeYOmovvhoK5WeYGWUsd8V72zmsyHB7XO94YgJVjvxfzn5K8bLePjFzwoSJjZvhBJ/ZQ05d8VmbvgyWUoPdG9oEa4fZ/lCYrXoaFdTot2xcJvrb/ZuiRl4s4eZpNeFYvVK/Am7UeFPAgMBAAECgYAUetOfzLYUudofvPCaKHu7tKZ5kQPfEa0w6BAPnBF1Mfl1JiDBRDMryFtKs6AOIAVwx00dY/Ex0BCbB3+Cr58H7t4NaPTJxCpmR09pK7o17B7xAdQv8+SynFNud9/5vQ5AEXMOLNwKiU7wpXT6Z7ZIibUBOR7ewsWgsHCDpN1iqQJBAOMODPTPSiQMwRAUHIc6GPleFSJnIz2PAoG3JOG9KFAL6RtIc19lob2ZXdbQdzKtjSkWo+O5W20WDNAl1k32h6MCQQC7W4ZCIY67mPbL6CxXfHjpSGF4Dr9VWJ7ZrKHr6XUoOIcEvsn/pHvWonjMdy93rQMSfOE8BKd/I1+GHRmNVgplAkAnSo4paxmsZVyfeKt7Jy2dMY+8tVZe17maUuQaAE7Sk00SgJYegwrbMYgQnWCTL39HBfj0dmYA2Zj8CCAuu6O7AkEAryFiYjaUAO9+4iNoL27+ZrFtypeeadyov7gKs0ZKaQpNyzW8A+Zwi7TbTeSqzic/E+z/bOa82q7p/6b7141xsQJBANCAcIwMcVb6KVCHlQbOtKspo5Eh4ZQi8bGl+IcwbQ6JSxeTx915IfAldgbuU047wOB04dYCFB2yLDiUGVXTifU=\n-----END PRIVATE KEY-----\n",
                "client_email": "dummy@dummy.iam.gserviceaccount.com",
            },
            "secure_devices_pin": secure_pin,
        }
    )
    config = GoogleConfig(hass, secure_config)

    assert config.secure_devices_pin == secure_pin


async def test_should_expose(hass):
    """Test the google config should expose method."""
    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()

    with patch.object(config, "async_call_homegraph_api"):
        # Wait for google_assistant.helpers.async_initialize.sync_google to be called
        await hass.async_block_till_done()

    assert (
        config.should_expose(State(DOMAIN + ".mock", "mock", {"view": "not None"}))
        is False
    )

    with patch.object(config, "async_call_homegraph_api"):
        # Wait for google_assistant.helpers.async_initialize.sync_google to be called
        await hass.async_block_till_done()

    assert config.should_expose(State(CLOUD_NEVER_EXPOSED_ENTITIES[0], "mock")) is False


async def test_missing_service_account(hass):
    """Test the google config _async_request_sync_devices."""
    incorrect_config = GOOGLE_ASSISTANT_SCHEMA(
        {
            "project_id": "1234",
        }
    )
    config = GoogleConfig(hass, incorrect_config)
    await config.async_initialize()

    with patch.object(config, "async_call_homegraph_api"):
        # Wait for google_assistant.helpers.async_initialize.sync_google to be called
        await hass.async_block_till_done()

    assert (
        await config._async_request_sync_devices("mock")
        is HTTPStatus.INTERNAL_SERVER_ERROR
    )
    renew = config._access_token_renew
    await config._async_update_token()
    assert config._access_token_renew is renew


async def test_async_enable_local_sdk(hass, hass_client, hass_storage, caplog):
    """Test the google config enable and disable local sdk."""
    command_events = async_capture_events(hass, EVENT_COMMAND_RECEIVED)
    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    hass.states.async_set("light.ceiling_lights", "off")

    assert await async_setup_component(hass, "webhook", {})

    hass_storage["google_assistant"] = {
        "version": 1,
        "minor_version": 1,
        "key": "google_assistant",
        "data": {
            "agent_user_ids": {
                "agent_1": {
                    "local_webhook_id": "mock_webhook_id",
                },
            },
        },
    }
    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()

    with patch.object(config, "async_call_homegraph_api"):
        # Wait for google_assistant.helpers.async_initialize.sync_google to be called
        await hass.async_block_till_done()

    assert config.is_local_sdk_active is True

    client = await hass_client()

    resp = await client.post(
        "/api/webhook/mock_webhook_id",
        json={
            "inputs": [
                {
                    "context": {"locale_country": "US", "locale_language": "en"},
                    "intent": "action.devices.EXECUTE",
                    "payload": {
                        "commands": [
                            {
                                "devices": [{"id": "light.ceiling_lights"}],
                                "execution": [
                                    {
                                        "command": "action.devices.commands.OnOff",
                                        "params": {"on": True},
                                    }
                                ],
                            }
                        ],
                        "structureData": {},
                    },
                }
            ],
            "requestId": "mock_req_id",
        },
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result["requestId"] == "mock_req_id"

    assert len(command_events) == 1
    assert command_events[0].context.user_id == "agent_1"

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].context is command_events[0].context

    config.async_disable_local_sdk()
    assert config.is_local_sdk_active is False

    config._store._data = {
        STORE_AGENT_USER_IDS: {
            "agent_1": {STORE_GOOGLE_LOCAL_WEBHOOK_ID: "mock_webhook_id"},
            "agent_2": {STORE_GOOGLE_LOCAL_WEBHOOK_ID: "mock_webhook_id"},
        },
    }
    config.async_enable_local_sdk()
    assert config.is_local_sdk_active is False

    config._store._data = {
        STORE_AGENT_USER_IDS: {
            "agent_1": {STORE_GOOGLE_LOCAL_WEBHOOK_ID: None},
        },
    }
    config.async_enable_local_sdk()
    assert config.is_local_sdk_active is False

    config._store._data = {
        STORE_AGENT_USER_IDS: {
            "agent_2": {STORE_GOOGLE_LOCAL_WEBHOOK_ID: "mock_webhook_id"},
            "agent_1": {STORE_GOOGLE_LOCAL_WEBHOOK_ID: None},
        },
    }
    config.async_enable_local_sdk()
    assert config.is_local_sdk_active is False

    config.async_disable_local_sdk()

    config._store._data = {
        STORE_AGENT_USER_IDS: {
            "agent_1": {STORE_GOOGLE_LOCAL_WEBHOOK_ID: "mock_webhook_id"},
        },
    }
    config.async_enable_local_sdk()

    config._store.pop_agent_user_id("agent_1")

    caplog.clear()

    resp = await client.post(
        "/api/webhook/mock_webhook_id",
        json={
            "inputs": [
                {
                    "context": {"locale_country": "US", "locale_language": "en"},
                    "intent": "action.devices.EXECUTE",
                    "payload": {
                        "commands": [
                            {
                                "devices": [{"id": "light.ceiling_lights"}],
                                "execution": [
                                    {
                                        "command": "action.devices.commands.OnOff",
                                        "params": {"on": True},
                                    }
                                ],
                            }
                        ],
                        "structureData": {},
                    },
                }
            ],
            "requestId": "mock_req_id",
        },
    )
    assert resp.status == HTTPStatus.OK
    assert (
        "Cannot process request for webhook mock_webhook_id as no linked agent user is found:"
        in caplog.text
    )
