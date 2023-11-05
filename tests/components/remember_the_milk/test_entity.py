"""Test the Remember The Milk entity."""

from typing import Any
from unittest.mock import MagicMock, call

from aiortm import AioRTMError, AuthError
import pytest

from homeassistant.components.remember_the_milk import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import PROFILE

from tests.common import MockConfigEntry

CONFIG = {
    "name": f"{PROFILE}",
    "api_key": "test-api-key",
    "shared_secret": "test-shared-secret",
}


@pytest.mark.usefixtures("storage")
@pytest.mark.parametrize(
    ("check_token_side_effect", "entity_state"),
    [(None, "ok"), (AuthError("Invalid token!"), "API token invalid")],
)
async def test_entity_state(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    check_token_side_effect: Exception | None,
    entity_state: str,
) -> None:
    """Test the entity state."""
    client.rtm.api.check_token.side_effect = check_token_side_effect
    await hass.config_entries.async_setup(config_entry.entry_id)
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
            (1, 2, 3),
            f"{PROFILE}_create_task",
            {"name": "Test 1"},
            0,
            None,
            1,
            "rtm.tasks.add",
            1,
            call(
                timeline=1234,
                name="Test 1",
                parse=True,
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
                timeline=1234,
                name="Test 1",
                parse=True,
            ),
            "set_rtm_id",
            1,
            call(PROFILE, "test_1", 1, 2, 3),
        ),
        (
            (1, 2, 3),
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            1,
            call(PROFILE, "test_1"),
            1,
            "rtm.tasks.set_name",
            1,
            call(
                name="Test 1",
                list_id=1,
                taskseries_id=2,
                task_id=3,
                timeline=1234,
            ),
            "set_rtm_id",
            0,
            None,
        ),
        (
            (1, 2, 3),
            f"{PROFILE}_complete_task",
            {"id": "test_1"},
            1,
            call(PROFILE, "test_1"),
            1,
            "rtm.tasks.complete",
            1,
            call(
                list_id=1,
                taskseries_id=2,
                task_id=3,
                timeline=1234,
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
            (1, 2, 3),
            f"{PROFILE}_create_task",
            {"name": "Test 1"},
            "rtm.timelines.create",
            AioRTMError("Boom!"),
            "Error creating new Remember The Milk task for account myprofile: Boom!",
        ),
        (
            (1, 2, 3),
            f"{PROFILE}_create_task",
            {"name": "Test 1"},
            "rtm.tasks.add",
            AioRTMError("Boom!"),
            "Error creating new Remember The Milk task for account myprofile: Boom!",
        ),
        (
            None,
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            "rtm.timelines.create",
            AioRTMError("Boom!"),
            "Error creating new Remember The Milk task for account myprofile: Boom!",
        ),
        (
            None,
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            "rtm.tasks.add",
            AioRTMError("Boom!"),
            "Error creating new Remember The Milk task for account myprofile: Boom!",
        ),
        (
            (1, 2, 3),
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            "rtm.timelines.create",
            AioRTMError("Boom!"),
            "Error creating new Remember The Milk task for account myprofile: Boom!",
        ),
        (
            (1, 2, 3),
            f"{PROFILE}_create_task",
            {"name": "Test 1", "id": "test_1"},
            "rtm.tasks.set_name",
            AioRTMError("Boom!"),
            "Error creating new Remember The Milk task for account myprofile: Boom!",
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
            (1, 2, 3),
            f"{PROFILE}_complete_task",
            {"id": "test_1"},
            "rtm.timelines.create",
            AioRTMError("Boom!"),
            "Error completing task with id test_1 for account myprofile: Boom!",
        ),
        (
            (1, 2, 3),
            f"{PROFILE}_complete_task",
            {"id": "test_1"},
            "rtm.tasks.complete",
            AioRTMError("Boom!"),
            "Error completing task with id test_1 for account myprofile: Boom!",
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
