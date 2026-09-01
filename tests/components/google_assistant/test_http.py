"""Test Google http services."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
import json
from pathlib import Path
from typing import Any
from unittest.mock import ANY, call, patch
from uuid import uuid4

import pytest

from homeassistant.components.google_assistant import GOOGLE_ASSISTANT_SCHEMA, helpers
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
    GoogleConfigStore,
    _get_homegraph_jwt,
    _get_homegraph_token,
    async_get_users,
)
from homeassistant.components.homeassistant.const import DATA_EXPOSED_ENTITIES
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EntityCategory,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
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


async def test_should_expose_uses_exposed_entities_store(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test should_expose delegates to the shared store for entities YAML doesn't cover."""
    config = GOOGLE_ASSISTANT_SCHEMA(
        {"project_id": "1234", "exposed_domains": ["light"]}
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()

    entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", suggested_object_id="ac"
    )
    hass.states.async_set(entry.entity_id, "on")

    async_expose_entity(hass, DOMAIN, entry.entity_id, False)
    assert google_config.should_expose(entry.entity_id) is False

    async_expose_entity(hass, DOMAIN, entry.entity_id, True)
    assert google_config.should_expose(entry.entity_id) is True


async def test_should_expose_applies_yaml_domain_exposure(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test should_expose exposes an entity matched by expose_by_default/exposed_domains."""
    entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    hass.states.async_set(entry.entity_id, "on")
    config = GOOGLE_ASSISTANT_SCHEMA(
        {"project_id": "1234", "exposed_domains": ["light"]}
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()

    # Reconciled eagerly against YAML once Home Assistant has started.
    assert google_config.should_expose(entry.entity_id) is True


async def test_should_expose_applies_yaml_explicit_exclude(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test an explicit entity_config exclude wins over a matching domain default."""
    entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    hass.states.async_set(entry.entity_id, "on")
    config = GOOGLE_ASSISTANT_SCHEMA(
        {
            "project_id": "1234",
            "exposed_domains": ["light"],
            "entity_config": {entry.entity_id: {"expose": False}},
        }
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()

    assert google_config.should_expose(entry.entity_id) is False


async def test_should_expose_applies_yaml_explicit_include(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test an explicit entity_config include applies even outside exposed_domains."""
    entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", suggested_object_id="ac"
    )
    hass.states.async_set(entry.entity_id, "on")
    config = GOOGLE_ASSISTANT_SCHEMA(
        {
            "project_id": "1234",
            "exposed_domains": ["light"],
            "entity_config": {entry.entity_id: {"expose": True}},
        }
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()

    assert google_config.should_expose(entry.entity_id) is True


async def test_should_expose_defers_to_ui_when_yaml_has_no_opinion(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test should_expose leaves an entity YAML doesn't mention to the shared store."""
    entry = entity_registry.async_get_or_create(
        "sensor", "test", "unique", suggested_object_id="not_exposed"
    )
    config = GOOGLE_ASSISTANT_SCHEMA(
        {"project_id": "1234", "exposed_domains": ["light"]}
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()

    # Not written by YAML reconciliation; falls through to (and is cached
    # by) the shared store's own generic fallback.
    assert google_config.should_expose(entry.entity_id) is False


async def test_should_expose_locks_yaml_matched_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a YAML-matched entity is locked against exposure changes from the UI."""
    entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    hass.states.async_set(entry.entity_id, "on")
    config = GOOGLE_ASSISTANT_SCHEMA(
        {"project_id": "1234", "exposed_domains": ["light"]}
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()

    assert google_config.should_expose(entry.entity_id) is True

    # A UI-driven change doesn't stick while YAML has an opinion.
    async_expose_entity(hass, DOMAIN, entry.entity_id, False)
    assert google_config.should_expose(entry.entity_id) is True


async def test_should_expose_clears_stale_yaml_exposure_on_unlock(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test becoming an auxiliary entity clears a previously locked exposure."""
    entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    hass.states.async_set(entry.entity_id, "on")
    config = GOOGLE_ASSISTANT_SCHEMA(
        {"project_id": "1234", "exposed_domains": ["light"]}
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()

    assert google_config.should_expose(entry.entity_id) is True

    entity_registry.async_update_entity(
        entry.entity_id, entity_category=EntityCategory.DIAGNOSTIC
    )
    await hass.async_block_till_done()

    assert google_config.should_expose(entry.entity_id) is False


async def test_ui_exposure_change_persists_when_yaml_has_no_opinion(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a UI change to an entity YAML doesn't cover survives should_expose queries."""
    entry = entity_registry.async_get_or_create(
        "sensor", "test", "unique", suggested_object_id="not_exposed"
    )
    config = GOOGLE_ASSISTANT_SCHEMA(
        {"project_id": "1234", "exposed_domains": ["light"]}
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()

    async_expose_entity(hass, DOMAIN, entry.entity_id, True)

    assert google_config.should_expose(entry.entity_id) is True


async def test_new_entity_matching_yaml_domain_triggers_sync(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a newly registered entity matching exposed_domains schedules a sync."""
    config = GOOGLE_ASSISTANT_SCHEMA(
        {"project_id": "1234", "expose_by_default": True, "exposed_domains": ["light"]}
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()
    await google_config.async_connect_agent_user("mock-user-id")

    with (
        patch.object(google_config, "async_sync_entities") as mock_sync,
        patch.object(helpers, "SYNC_DELAY", 0),
    ):
        entry = entity_registry.async_get_or_create(
            "light", "test", "unique", suggested_object_id="kitchen"
        )
        hass.states.async_set(entry.entity_id, "on")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

    assert google_config.should_expose(entry.entity_id) is True
    mock_sync.assert_called_once_with("mock-user-id")


async def test_new_entity_exposed_via_expose_new_triggers_sync(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a newly registered entity exposed via expose_new schedules a sync."""
    config = GOOGLE_ASSISTANT_SCHEMA(
        {"project_id": "1234", "expose_by_default": False, "exposed_domains": []}
    )
    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()
    await google_config.async_connect_agent_user("mock-user-id")

    exposed_entities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_set_expose_new_entities(DOMAIN, True)

    with (
        patch.object(google_config, "async_sync_entities") as mock_sync,
        patch.object(helpers, "SYNC_DELAY", 0),
    ):
        entry = entity_registry.async_get_or_create(
            "light", "test", "unique", suggested_object_id="kitchen"
        )
        hass.states.async_set(entry.entity_id, "on")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

    mock_sync.assert_called_once_with("mock-user-id")


async def test_expose_update_triggers_sync(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that updating exposed entities schedules a Google sync."""
    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()
    await config.async_connect_agent_user("mock-user-id")

    # "light" is exposed by default; its YAML exposure is applied as soon
    # as its state is added, since the listener is already active.
    entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    hass.states.async_set(entry.entity_id, "on")
    assert config.should_expose(entry.entity_id) is True

    with (
        patch.object(config, "async_sync_entities") as mock_sync,
        patch.object(helpers, "SYNC_DELAY", 0),
    ):
        async_expose_entity(hass, DOMAIN, entry.entity_id, False)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

    mock_sync.assert_called_once_with("mock-user-id")


@pytest.mark.parametrize(
    ("update_kwargs", "expected_calls"),
    [
        pytest.param(
            {"aliases": ["Kitchen Light"]},
            [call("mock-user-id")],
            id="aliases_changed",
        ),
        pytest.param({"icon": "mdi:lightbulb"}, [], id="unrelated_field_changed"),
    ],
)
async def test_registry_update_triggers_sync_only_for_aliases(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    update_kwargs: dict[str, Any],
    expected_calls: list[Any],
) -> None:
    """Test only alias changes on an exposed entity schedule a Google sync."""
    config = GoogleConfig(hass, DUMMY_CONFIG)
    await config.async_initialize()
    await config.async_connect_agent_user("mock-user-id")

    # "light" is exposed by default; its YAML exposure is applied as soon
    # as its state is added, since the listener is already active.
    entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    hass.states.async_set(entry.entity_id, "on")
    assert config.should_expose(entry.entity_id) is True

    with (
        patch.object(config, "async_sync_entities") as mock_sync,
        patch.object(helpers, "SYNC_DELAY", 0),
    ):
        entity_registry.async_update_entity(entry.entity_id, **update_kwargs)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

    assert mock_sync.call_args_list == expected_calls


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


async def test_async_get_users_from_store(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test async_get_users from a store.

    This test ensures we can load from data saved by GoogleConfigStore.
    """
    store = GoogleConfigStore(hass)
    await store.async_initialize()

    store.add_agent_user_id("agent_1")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.google_assistant.http.json_util.load_json",
        return_value=hass_storage["google_assistant"],
    ):
        assert await async_get_users(hass) == ["agent_1"]


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
    hass: HomeAssistant, tmp_path: Path, store_data: str, expected_users: list[str]
) -> None:
    """Test async_get_users from stored JSON data."""
    hass.config.config_dir = str(tmp_path)
    path = tmp_path / STORAGE_DIR / GoogleConfigStore._STORAGE_KEY
    await hass.async_add_executor_job(path.parent.mkdir)
    await hass.async_add_executor_job(path.write_text, store_data)
    assert await async_get_users(hass) == expected_users
