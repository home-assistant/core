"""Test Google http services."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import ANY, patch
from uuid import uuid4

import py
import pytest

from homeassistant.components.google_assistant import GOOGLE_ASSISTANT_SCHEMA
from homeassistant.components.google_assistant.const import (
    EVENT_COMMAND_RECEIVED,
    HOMEGRAPH_TOKEN_URL,
    REPORT_STATE_BASE_URL,
    STORE_AGENT_USER_IDS,
    STORE_GOOGLE_LOCAL_WEBHOOK_ID,
)
from homeassistant.components.google_assistant.http import (
    GoogleConfig,
    GoogleConfigStore,
    _get_homegraph_jwt,
    _get_homegraph_token,
    async_get_users,
)
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
    async_test_home_assistant,
)
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

DUMMY_PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDHpAmcxB6bPA"
    "peq/upM27z/ml+gKghe8xsW0czDSb12p0T4cJgZ7UWlZfl1JmB+WPcvf3Gfe/q"
    "V5JPxjrQzT1oUP6wZKSH914MeWHImJcp+QhS7n0muGjYvi6VfMIkKvjKlqVVcd"
    "xV9bkWw+YOHhC+hUi0/rmQw8Dch2NMVMyNamt/PzU8FWQ61w4Bwe0jp0CbxWYk"
    "HWvDmxYrMXdFs2Q4LxWln8EGuytS9HZAIQxz/UBCBOXDA/q4OqQV/2hpnt6t0H"
    "Dlpp90YDoHw5d4ySgo80Iz6UDrFUt8G0MJq/8MaGgvOH+ZZ4CtcA/Xes7Uejwy"
    "/2jhe9dytlrE56z0NotxAgMBAAECggEAM/knDXpbM3OiiXoBls+Oi5PImAfbfX"
    "gSxITQ2OAMLAYhTYtBBMMK+FmyhUFfQ2CPGGkX16RyoJHyw7TqG/DKk00+uOJC"
    "mSkTgXDaPZRICkPMYHa4+ysYFJESZJVpn2vWgDtOyJtPTsudR2lxi2xVVJwzTP"
    "dhjOgBXggbGESdShUcDQj0NeooRfMrj7VMUy8uZ/KjTWXgPyTALVl1udvzGtmy"
    "2Q/PcUo2RMDKE9azWtV91qoSgiqF4je+IueeT5qgRKPF15r4OWiYv74zM7iseo"
    "lCgP0QXou+iD26gWnAGxLqo8nG7tqsyPSl0NP4oIwWvcbNP+Ys1+r+PtuGCOmB"
    "hwKBgQDujHrxccTHAmbxnPpxrai/8d24Mpul+IB34CBK3dSkePxHXitE9q6KhT"
    "fZaqTDfOzzU9B0P0ohx0U9DLC42m6sLCkCLDa4BEwgsaFG5e/mj+w36cNgt56r"
    "VKTyleNX4Dhq5oz3azyzVE6rQ8EzLNgvgiN6zr2Gy2+Y1aHFFkQPNwKBgQDWPu"
    "RixtIhapdqRs1g6R+4prVXzUDWmw1N8y0JJ8DJFSuAyrCblfKSZlrHLq0CZfEp"
    "2uNJ6+brmnDFo0XMwyhOi8Q4EIx/bZr+tK+ZLJ34ZRuzasglALGdYtLfo3T3A7"
    "Ca6ThLMy1V+FZPUOP3bgjqmFViQ+/bPdHFrjeCr0/+lwKBgQCxvnrc7KhyoJeT"
    "8COsEHlsjAto9EyFnmQa7iUho6iN5JgVlVUoTaZAEINMvOmHv83OgOURuRbDlH"
    "dCxfHnytor77ueotMiyhDvS2ugKDRY12RrRQMPTcIsZyWAm66KC8f930uqD31r"
    "IaZ8dj++oetzesR0/Ra7GVpNxuCCudR8gQKBgBqO2UjVVJ8H05U9CaCFxYTiRY"
    "CI1QzFU7Th/CcyYleK5EWm2pWu1M8JGR+vzYqKkIabt6kmMQ3rqycUwkZLuudh"
    "tAUvJ/tz3s7MHyhhu4NbJT/scLsFhv73jSRj4s/sCSxq1KudwHTzv989K8U0Qq"
    "6yC4OO4GDRHPvgSMlOaiApAoGBANOE05ONrxrWTKfn+ydTDOIyIlXdVDG0twDE"
    "vuUvo/6+5BxvuZ0N+s333DA2iRDbfTCTnJizOC/NSGGxzfJ3D6lYOp2a/iC1t3"
    "IC0fOw+YC6Gq6kN+qaIcyM0Nmsa7rG72Nq987HDwHwL41HLXTDuQEfqO4DsQgC"
    "WKkTkZh32J2/\n"
    "-----END PRIVATE KEY-----\n"
)
DUMMY_CONFIG = GOOGLE_ASSISTANT_SCHEMA(
    {
        "project_id": "1234",
        "service_account": {
            "private_key": DUMMY_PRIVATE_KEY,
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


async def test_sync_google_does_not_block_startup(hass: HomeAssistant) -> None:
    """Test that Google entity sync runs after startup, not during."""
    hass.set_state(CoreState.not_running)
    config = GoogleConfig(hass, DUMMY_CONFIG)

    with patch.object(config, "async_sync_entities_all") as mock_sync:
        await config.async_initialize()

        # Fire EVENT_HOMEASSISTANT_START - sync should NOT run yet
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        mock_sync.assert_not_called()

        # Fire EVENT_HOMEASSISTANT_STARTED - now sync should run
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        mock_sync.assert_called_once()


async def test_get_jwt(hass: HomeAssistant) -> None:
    """Test signing of key."""

    jwt = (
        "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJkdW1teUBkdW1teS5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsInN"
        "jb3BlIjoiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vYXV0aC9ob21lZ3JhcG"
        "giLCJhdWQiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20vby9vYXV0aDIvd"
        "G9rZW4iLCJpYXQiOjE1NzEwMTEyMDAsImV4cCI6MTU3MTAxNDgwMH0."
        "Tt88OV1IndxiJLdBTPBCW5AlsWWlBRAU9bK8c28PlYSlJBHRd0dQCjYh-4lL1t-"
        "RfrLJCqiq9_O9xa4n7Ge59xM9pb_ifFCaYzkUpJlVy5XJYVu7hE-0AV_xAygKjN"
        "7nVLpcCFsygoh-sr2bkJpDKzcEpPRlH2lAjkMisVVibt_-oix9m0KO0qZ-7uqV5"
        "YG2uLiHvolJ0F2oSc4MJGIOTG7Hf3qWSk_MiVLD0t1Jdp1xniHLzlYht0xSVZ0m"
        "b1wflqM9VwERuAbCzXRabNJs85XzeR8aOwk38xwobUk0JXSAaNISoQTC47OwEY8"
        "DvSmDgMbYf5aG5yEKCZnYngt6Pg"
    )
    res = _get_homegraph_jwt(
        datetime(2019, 10, 14, tzinfo=UTC),
        DUMMY_CONFIG["service_account"]["client_email"],
        DUMMY_CONFIG["service_account"]["private_key"],
    )
    assert res == jwt


async def test_get_access_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_update_access_token(hass: HomeAssistant) -> None:
    """Test the function to update access token when expired."""
    jwt = "dummyjwt"

    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()

    base_time = datetime(2019, 10, 14, tzinfo=UTC)
    with (
        patch(
            "homeassistant.components.google_assistant.http._get_homegraph_token"
        ) as mock_get_token,
        patch(
            "homeassistant.components.google_assistant.http._get_homegraph_jwt"
        ) as mock_get_jwt,
        patch(
            "homeassistant.core.dt_util.utcnow",
        ) as mock_utcnow,
    ):
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


async def test_call_homegraph_api(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
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


async def test_call_homegraph_api_retry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
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


async def test_report_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
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


async def test_report_event(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """Test the report event function."""
    agent_user_id = "user"
    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()

    await config.async_connect_agent_user(agent_user_id)
    message = {"devices": {}}

    with patch.object(config, "async_call_homegraph_api"):
        # Wait for google_assistant.helpers.async_initialize.sync_google to be called
        await hass.async_block_till_done()

    event_id = uuid4().hex
    with patch.object(config, "async_call_homegraph_api") as mock_call:
        # Wait for google_assistant.helpers.async_initialize.sync_google to be called
        await config.async_report_state(message, agent_user_id, event_id=event_id)
        mock_call.assert_called_once_with(
            REPORT_STATE_BASE_URL,
            {
                "requestId": ANY,
                "agentUserId": agent_user_id,
                "payload": message,
                "eventId": event_id,
            },
        )


async def test_google_config_local_fulfillment(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
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
    assert config.get_local_user_id(local_webhook_id) == agent_user_id
    assert config.get_local_user_id("INCORRECT") is None


async def test_secure_device_pin_config(hass: HomeAssistant) -> None:
    """Test the setting of the secure device pin configuration."""
    secure_pin = "TEST"
    secure_config = GOOGLE_ASSISTANT_SCHEMA(
        {
            "project_id": "1234",
            "service_account": {
                "private_key": DUMMY_PRIVATE_KEY,
                "client_email": "dummy@dummy.iam.gserviceaccount.com",
            },
            "secure_devices_pin": secure_pin,
        }
    )
    config = GoogleConfig(hass, secure_config)

    assert config.secure_devices_pin == secure_pin


async def test_missing_service_account(hass: HomeAssistant) -> None:
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


async def test_async_enable_local_sdk(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
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
        "Cannot process request for webhook **REDACTED**"
        " as no linked agent user is found:" in caplog.text
    )


async def test_agent_user_id_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test a disconnect message."""

    hass_storage["google_assistant"] = {
        "version": 1,
        "minor_version": 1,
        "key": "google_assistant",
        "data": {
            "agent_user_ids": {
                "agent_1": {
                    "local_webhook_id": "test_webhook",
                }
            },
        },
    }

    store = GoogleConfigStore(hass)
    await store.async_initialize()

    assert hass_storage["google_assistant"] == {
        "version": 1,
        "minor_version": 2,
        "key": "google_assistant",
        "data": {
            "agent_user_ids": {
                "agent_1": {
                    "local_webhook_id": "test_webhook",
                }
            },
        },
    }

    async def _check_after_delay(data):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
        await hass.async_block_till_done()

        assert (
            list(hass_storage["google_assistant"]["data"]["agent_user_ids"].keys())
            == data
        )

    store.add_agent_user_id("agent_2")
    await _check_after_delay(["agent_1", "agent_2"])

    store.pop_agent_user_id("agent_1")
    await _check_after_delay(["agent_2"])

    hass_storage["google_assistant"] = {
        "version": 1,
        "minor_version": 2,
        "key": "google_assistant",
        "data": {
            "agent_user_ids": {"agent_1": {}},
        },
    }
    store = GoogleConfigStore(hass)
    await store.async_initialize()

    assert (
        STORE_GOOGLE_LOCAL_WEBHOOK_ID
        in hass_storage["google_assistant"]["data"]["agent_user_ids"]["agent_1"]
    )


async def test_async_get_users_no_store(hass: HomeAssistant) -> None:
    """Test async_get_users when there is no store."""
    assert await async_get_users(hass) == []


async def test_async_get_users_from_store(tmpdir: py.path.local) -> None:
    """Test async_get_users from a store.

    This test ensures we can load from data saved by GoogleConfigStore.
    """
    async with async_test_home_assistant() as hass:
        hass.config.config_dir = await hass.async_add_executor_job(
            tmpdir.mkdir, "temp_storage"
        )

        store = GoogleConfigStore(hass)
        await store.async_initialize()

        store.add_agent_user_id("agent_1")
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
        await hass.async_block_till_done()

        assert await async_get_users(hass) == ["agent_1"]

        await hass.async_stop()


VALID_STORE_DATA = json.dumps(
    {
        "version": 1,
        "minor_version": 2,
        "key": "google_assistant",
        "data": {
            "agent_user_ids": {"agent_1": {}},
        },
    }
)


NO_DATA = json.dumps(
    {
        "version": 1,
        "minor_version": 2,
        "key": "google_assistant",
    }
)


DATA_NOT_DICT = json.dumps(
    {
        "version": 1,
        "minor_version": 2,
        "key": "google_assistant",
        "data": "hello",
    }
)


NO_AGENT_USER_IDS = json.dumps(
    {
        "version": 1,
        "minor_version": 2,
        "key": "google_assistant",
        "data": {},
    }
)


AGENT_USER_IDS_NOT_DICT = json.dumps(
    {
        "version": 1,
        "minor_version": 2,
        "key": "google_assistant",
        "data": {
            "agent_user_ids": "hello",
        },
    }
)


@pytest.mark.parametrize(
    ("store_data", "expected_users"),
    [
        (VALID_STORE_DATA, ["agent_1"]),
        ("", []),
        ("not_a_dict", []),
        (NO_DATA, []),
        (DATA_NOT_DICT, []),
        (NO_AGENT_USER_IDS, []),
        (AGENT_USER_IDS_NOT_DICT, []),
    ],
)
async def test_async_get_users(
    tmpdir: py.path.local, store_data: str, expected_users: list[str]
) -> None:
    """Test async_get_users from stored JSON data."""
    async with async_test_home_assistant() as hass:
        hass.config.config_dir = await hass.async_add_executor_job(
            tmpdir.mkdir, "temp_storage"
        )
        path = hass.config.config_dir / ".storage" / GoogleConfigStore._STORAGE_KEY
        os.makedirs(os.path.dirname(path), exist_ok=True)
        await hass.async_add_executor_job(Path(path).write_text, store_data)
        assert await async_get_users(hass) == expected_users

        await hass.async_stop()
