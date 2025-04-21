"""Test the Remember The Milk entity."""

from typing import Any
from unittest.mock import MagicMock, call

import pytest
from rtmapi import RtmRequestFailedException

from homeassistant.components.remember_the_milk import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import CONFIG, PROFILE


@pytest.mark.parametrize(
    ("valid_token", "entity_state"), [(True, "ok"), (False, "API token invalid")]
)
async def test_entity_state(
    hass: HomeAssistant,
    client: MagicMock,
    storage: MagicMock,
    valid_token: bool,
    entity_state: str,
) -> None:
    """Test the entity state."""
    client.token_valid.return_value = valid_token
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: CONFIG})
    entity_id = f"{DOMAIN}.{PROFILE}"
    state = hass.states.get(entity_id)

    assert state
    assert state.state == entity_state


@pytest.mark.parametrize(
    (
        "get_rtm_id_return_value",
        "service",
        "service_data",
        "get_rtm_id_call_count",
        "get_rtm_id_call_args",
        "timelines_call_count",
        "api_method",
        "api_method_call_count",
        "api_method_call_args",
        "storage_method",
        "storage_method_call_count",
        "storage_method_call_args",
    ),
    [
        (
            ("1", "2", "3"),
            f"{PROFILE}_create_task",
            {"name": "Test 1"},
            0,
            None,
            1,
            "rtm.tasks.add",
            1,
            call(
                timeline="1234",
                name="Test 1",
                parse="1",
            ),
            "set_rtm_id",
            0,
            None,
        ),
        (
            None,
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            1,
            call(PROFILE, "test_1"),
            1,
            "rtm.tasks.add",
            1,
            call(
                timeline="1234",
                name="Test 1",
                parse="1",
            ),
            "set_rtm_id",
            1,
            call(PROFILE, "test_1", "1", "2", "3"),
        ),
        (
            ("1", "2", "3"),
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            1,
            call(PROFILE, "test_1"),
            1,
            "rtm.tasks.setName",
            1,
            call(
                name="Test 1",
                list_id="1",
                taskseries_id="2",
                task_id="3",
                timeline="1234",
            ),
            "set_rtm_id",
            0,
            None,
        ),
        (
            ("1", "2", "3"),
            f"{PROFILE}_complete_task",
            {"id": "test_1"},
            1,
            call(PROFILE, "test_1"),
            1,
            "rtm.tasks.complete",
            1,
            call(
                list_id="1",
                taskseries_id="2",
                task_id="3",
                timeline="1234",
            ),
            "delete_rtm_id",
            1,
            call(PROFILE, "test_1"),
        ),
    ],
)
async def test_services(
    hass: HomeAssistant,
    client: MagicMock,
    storage: MagicMock,
    get_rtm_id_return_value: Any,
    service: str,
    service_data: dict[str, Any],
    get_rtm_id_call_count: int,
    get_rtm_id_call_args: tuple[tuple, dict] | None,
    timelines_call_count: int,
    api_method: str,
    api_method_call_count: int,
    api_method_call_args: tuple[tuple, dict],
    storage_method: str,
    storage_method_call_count: int,
    storage_method_call_args: tuple[tuple, dict] | None,
) -> None:
    """Test create and complete task service."""
    storage.get_rtm_id.return_value = get_rtm_id_return_value
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: CONFIG})

    await hass.services.async_call(DOMAIN, service, service_data, blocking=True)

    assert storage.get_rtm_id.call_count == get_rtm_id_call_count
    assert storage.get_rtm_id.call_args == get_rtm_id_call_args
    assert client.rtm.timelines.create.call_count == timelines_call_count
    client_method = client
    for name in api_method.split("."):
        client_method = getattr(client_method, name)
    assert client_method.call_count == api_method_call_count
    assert client_method.call_args == api_method_call_args
    storage_method_attribute = getattr(storage, storage_method)
    assert storage_method_attribute.call_count == storage_method_call_count
    assert storage_method_attribute.call_args == storage_method_call_args


@pytest.mark.parametrize(
    (
        "get_rtm_id_return_value",
        "service",
        "service_data",
        "method",
        "exception",
        "error_message",
    ),
    [
        (
            ("1", "2", "3"),
            f"{PROFILE}_create_task",
            {"name": "Test 1"},
            "rtm.timelines.create",
            RtmRequestFailedException("rtm.timelines.create", "400", "Bad request"),
            "Request rtm.timelines.create failed. Status: 400, reason: Bad request.",
        ),
        (
            ("1", "2", "3"),
            f"{PROFILE}_create_task",
            {"name": "Test 1"},
            "rtm.tasks.add",
            RtmRequestFailedException("rtm.tasks.add", "400", "Bad request"),
            "Request rtm.tasks.add failed. Status: 400, reason: Bad request.",
        ),
        (
            None,
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            "rtm.timelines.create",
            RtmRequestFailedException("rtm.timelines.create", "400", "Bad request"),
            "Request rtm.timelines.create failed. Status: 400, reason: Bad request.",
        ),
        (
            None,
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            "rtm.tasks.add",
            RtmRequestFailedException("rtm.tasks.add", "400", "Bad request"),
            "Request rtm.tasks.add failed. Status: 400, reason: Bad request.",
        ),
        (
            ("1", "2", "3"),
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            "rtm.timelines.create",
            RtmRequestFailedException("rtm.timelines.create", "400", "Bad request"),
            "Request rtm.timelines.create failed. Status: 400, reason: Bad request.",
        ),
        (
            ("1", "2", "3"),
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            "rtm.tasks.setName",
            RtmRequestFailedException("rtm.tasks.setName", "400", "Bad request"),
            "Request rtm.tasks.setName failed. Status: 400, reason: Bad request.",
        ),
        (
            None,
            f"{PROFILE}_complete_task",
            {"id": "test_1"},
            "rtm.timelines.create",
            None,
            (
                f"Could not find task with ID test_1 in account {PROFILE}. "
                "So task could not be closed"
            ),
        ),
        (
            ("1", "2", "3"),
            f"{PROFILE}_complete_task",
            {"id": "test_1"},
            "rtm.timelines.create",
            RtmRequestFailedException("rtm.timelines.create", "400", "Bad request"),
            "Request rtm.timelines.create failed. Status: 400, reason: Bad request.",
        ),
        (
            ("1", "2", "3"),
            f"{PROFILE}_complete_task",
            {"id": "test_1"},
            "rtm.tasks.complete",
            RtmRequestFailedException("rtm.tasks.complete", "400", "Bad request"),
            "Request rtm.tasks.complete failed. Status: 400, reason: Bad request.",
        ),
    ],
)
async def test_services_errors(
    hass: HomeAssistant,
    client: MagicMock,
    storage: MagicMock,
    caplog: pytest.LogCaptureFixture,
    get_rtm_id_return_value: Any,
    service: str,
    service_data: dict[str, Any],
    method: str,
    exception: Exception,
    error_message: str,
) -> None:
    """Test create and complete task service errors."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: CONFIG})
    storage.get_rtm_id.return_value = get_rtm_id_return_value

    client_method = client
    for name in method.split("."):
        client_method = getattr(client_method, name)

    client_method.side_effect = exception

    await hass.services.async_call(DOMAIN, service, service_data, blocking=True)

    assert error_message in caplog.text
