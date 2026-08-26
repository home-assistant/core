"""Test schlage lock."""

from collections.abc import Awaitable, Callable
from datetime import datetime as dt_datetime
from typing import Any
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pyschlage.code import (
    AccessCode,
    MultiRecurringSchedule,
    RecurringSchedule,
    TemporarySchedule,
)
from pyschlage.exceptions import Error as SchlageError
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.components.schlage.const import (
    DOMAIN,
    SERVICE_ADD_CODE,
    SERVICE_DELETE_CODE,
    SERVICE_GET_CODES,
    SERVICE_UPDATE_CODE,
    UPDATE_INTERVAL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import MockSchlageConfigEntry

from tests.common import async_fire_time_changed, snapshot_platform


async def test_lock_attributes(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockSchlageConfigEntry]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test lock attributes."""
    with patch("homeassistant.components.schlage.PLATFORMS", [Platform.LOCK]):
        config_entry = await mock_add_config_entry()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_lock_jammed(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test lock jammed state."""
    mock_lock.is_locked = False
    mock_lock.is_jammed = True
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    lock = hass.states.get("lock.vault_door")
    assert lock is not None
    assert lock.state == LockState.JAMMED


async def test_lock_disconnected(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test lock unavailable when disconnected."""
    mock_lock.connected = False
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    lock = hass.states.get("lock.vault_door")
    assert lock is not None
    assert lock.state == STATE_UNAVAILABLE


async def test_lock_services(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test lock services."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        service_data={ATTR_ENTITY_ID: "lock.vault_door"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.lock.assert_called_once_with()

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        service_data={ATTR_ENTITY_ID: "lock.vault_door"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.unlock.assert_called_once_with()

    await hass.config_entries.async_unload(mock_added_config_entry.entry_id)


async def test_changed_by(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test population of the changed_by attribute."""
    mock_lock.last_changed_by.reset_mock()
    mock_lock.last_changed_by.return_value = "access code - foo"
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    lock = hass.states.get("lock.vault_door")
    assert lock is not None
    assert lock.attributes["changed_by"] == "access code - foo"


@pytest.mark.parametrize(
    "notify_on_use",
    [
        True,
        False,
    ],
    ids=["notify-true", "notify-false"],
)
async def test_add_code_service(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
    notify_on_use: bool,
) -> None:
    """Test add_code service."""
    # Mock access_codes as empty initially
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
            "code": "1234",
            "notify_on_use": notify_on_use,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify add_access_code was called with correct AccessCode
    mock_lock.refresh_access_codes.assert_called_once()
    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args, AccessCode)
    assert call_args.name == "test_user"
    assert call_args.code == "1234"
    assert call_args.notify_on_use == notify_on_use


async def test_add_code_service_integer_code(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code service with an integer code."""
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
            "code": 1234,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lock.refresh_access_codes.assert_called_once()
    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args, AccessCode)
    assert call_args.name == "test_user"
    assert call_args.code == "1234"


async def test_add_code_service_default_notify_on_use_value(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code service."""
    # Mock access_codes as empty initially
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
            "code": "1234",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify add_access_code was called with correct AccessCode
    mock_lock.refresh_access_codes.assert_called_once()
    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args, AccessCode)
    assert call_args.name == "test_user"
    assert call_args.code == "1234"
    assert call_args.notify_on_use


async def test_add_code_service_temporary_schedule(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code creates TemporarySchedule when both dates provided."""
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
            "code": "1234",
            "notify_on_use": False,
            "start_datetime": dt_datetime(2025, 1, 1, 0, 0),
            "end_datetime": dt_datetime(2025, 6, 30, 23, 59),
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args, AccessCode)
    assert call_args.name == "test_user"
    assert call_args.code == "1234"
    assert isinstance(call_args.schedule, TemporarySchedule)
    assert call_args.schedule.start == dt_util.as_utc(dt_datetime(2025, 1, 1, 0, 0))
    assert call_args.schedule.end == dt_util.as_utc(dt_datetime(2025, 6, 30, 23, 59))


async def test_add_code_service_permanent_code(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code creates permanent code when neither date provided."""
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
            "code": "1234",
            "notify_on_use": False,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args, AccessCode)
    assert call_args.name == "test_user"
    assert call_args.code == "1234"
    assert call_args.schedule is None


async def test_add_code_service_one_date_only_raises(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code raises when only one date is provided (XOR)."""
    mock_lock.access_codes = {}

    with pytest.raises(
        ServiceValidationError,
        match="Start and end times are required together",
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": "1234",
                "start_datetime": dt_datetime(2025, 1, 1),
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_temporary_dates_required"


async def test_add_code_fails_with_start_after_end(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code raises when start_datetime is after end_datetime."""
    mock_lock.access_codes = {}

    with pytest.raises(
        ServiceValidationError,
        match="Start time must be before end time",
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": "1234",
                "start_datetime": dt_datetime(2025, 12, 31, 23, 59),
                "end_datetime": dt_datetime(2025, 1, 1),
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_start_after_end"


async def test_add_code_succeeds_with_valid_dates(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code succeeds when start is before end."""
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
            "code": "1234",
            "start_datetime": dt_datetime(2025, 1, 1),
            "end_datetime": dt_datetime(2025, 12, 31, 23, 59),
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args, AccessCode)
    assert call_args.name == "test_user"
    assert call_args.code == "1234"
    assert isinstance(call_args.schedule, TemporarySchedule)
    assert call_args.schedule.start == dt_util.as_utc(dt_datetime(2025, 1, 1))
    assert call_args.schedule.end == dt_util.as_utc(dt_datetime(2025, 12, 31, 23, 59))


@pytest.mark.parametrize(
    "code",
    [
        "abc",
        "123",
        "123456789",
        "12ab",
    ],
    ids=["non_digits", "too_short", "too_long", "mixed"],
)
async def test_add_code_service_invalid_code(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
    code: str,
) -> None:
    """Test add_code service rejects invalid PIN codes."""
    mock_lock.access_codes = {}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": code,
                "notify_on_use": False,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(["1", "2", "3", "4"], id="list"),
        pytest.param({"a": "b"}, id="dict"),
    ],
)
async def test_add_code_service_non_string_code(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
    code: Any,
) -> None:
    """Test add_code service rejects non-string code values with clean error."""
    mock_lock.access_codes = {}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": code,
                "notify_on_use": False,
            },
            blocking=True,
        )


async def test_add_code_service_duplicate_name(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code service with duplicate name."""

    # Mock existing access code
    existing_code = Mock()
    existing_code.name = "test_user"
    existing_code.code = "5678"
    mock_lock.access_codes = {"1": existing_code}

    with pytest.raises(
        ServiceValidationError,
        match='A PIN code with the name "test_user" already exists on the lock',
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": "1234",
                "notify_on_use": False,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_name_exists"
    assert exc_info.value.translation_placeholders == {"name": "test_user"}


async def test_add_code_service_duplicate_code(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code service with duplicate code."""
    # Mock existing access code

    existing_code = Mock()
    existing_code.name = "existing_user"
    existing_code.code = "1234"
    mock_lock.access_codes = {"1": existing_code}

    with pytest.raises(
        ServiceValidationError,
        match="A PIN code with this value already exists on the lock",
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": "1234",
                "notify_on_use": False,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_code_exists"


async def test_delete_code_service(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test delete_code service."""
    # Mock existing access code
    existing_code = Mock()
    existing_code.name = "test_user"
    existing_code.delete = Mock()
    mock_lock.access_codes = {"1": existing_code}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    existing_code.delete.assert_called_once()
    mock_lock.refresh_access_codes.assert_called_once()


async def test_delete_code_service_case_insensitive(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test delete_code service is case insensitive."""
    # Mock existing access code
    existing_code = Mock()
    existing_code.name = "Test_User"
    existing_code.delete = Mock()
    mock_lock.access_codes = {"1": existing_code}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    existing_code.delete.assert_called_once()


async def test_delete_code_service_nonexistent_code(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test delete_code service with nonexistent code."""
    mock_lock.access_codes = {}

    # Should not raise an error, just return silently
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "nonexistent",
        },
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_delete_code_service_no_access_codes(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test delete_code service when access_codes is None."""
    mock_lock.access_codes = None

    # Should not raise an error, just return silently
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
        },
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_delete_code_service_no_identifier_with_zero_codes(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test delete_code raises error when no identifier given and lock has zero codes."""
    mock_lock.access_codes = {}

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_CODE,
            service_data={
                "entity_id": "lock.vault_door",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_delete_code_missing_identifier"


async def test_get_codes_service(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test get_codes service."""
    # Mock existing access codes
    code1 = Mock()
    code1.name = "user1"
    code1.code = "1234"
    code1.access_code_id = "id1"
    code1.disabled = False
    code1.notify_on_use = True
    code1.schedule = None
    code2 = Mock()
    code2.name = "user2"
    code2.code = "5678"
    code2.access_code_id = "id2"
    code2.disabled = False
    code2.notify_on_use = True
    code2.schedule = None
    mock_lock.access_codes = {"1": code1, "2": code2}

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_CODES,
        service_data={
            "entity_id": "lock.vault_door",
        },
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert response == {
        "lock.vault_door": {
            "1": {
                "name": "user1",
                "code": "1234",
                "access_code_id": "id1",
                "disabled": False,
                "notify_on_use": True,
                "schedule": None,
            },
            "2": {
                "name": "user2",
                "code": "5678",
                "access_code_id": "id2",
                "disabled": False,
                "notify_on_use": True,
                "schedule": None,
            },
        }
    }


async def test_get_codes_service_no_codes(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test get_codes service with no codes."""
    mock_lock.access_codes = None

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_CODES,
        service_data={
            "entity_id": "lock.vault_door",
        },
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert response == {"lock.vault_door": {}}


async def test_get_codes_service_empty_codes(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test get_codes service with empty codes dict."""
    mock_lock.access_codes = {}

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_CODES,
        service_data={
            "entity_id": "lock.vault_door",
        },
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert response == {"lock.vault_door": {}}


async def test_get_codes_service_temporary_schedule(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test get_codes returns type=temporary when code has a TemporarySchedule."""
    start = dt_datetime(2025, 1, 1, 0, 0)
    end = dt_datetime(2025, 6, 30, 23, 59)
    temp_code = Mock()
    temp_code.name = "temp_user"
    temp_code.code = "1111"
    temp_code.access_code_id = "id_temp"
    temp_code.disabled = False
    temp_code.notify_on_use = True
    temp_code.schedule = TemporarySchedule(start=start, end=end)
    mock_lock.access_codes = {"1": temp_code}

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_CODES,
        service_data={
            "entity_id": "lock.vault_door",
        },
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    schedule = response["lock.vault_door"]["1"]["schedule"]
    assert schedule["type"] == "temporary"
    assert schedule["start_datetime"] == start.isoformat()
    assert schedule["end_datetime"] == end.isoformat()


async def test_delete_code_service_nonexistent_code_with_existing_codes(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test delete_code service with nonexistent code when other codes exist."""
    # Mock existing access code with a different name
    existing_code = Mock()
    existing_code.name = "existing_user"
    existing_code.delete = Mock()
    mock_lock.access_codes = {"1": existing_code}

    # Try to delete a code that doesn't exist
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "nonexistent_user",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify that delete was not called on the existing code
    existing_code.delete.assert_not_called()


async def test_update_code_service_with_dates(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test update_code applies TemporarySchedule when both dates provided."""
    existing_code = Mock()
    existing_code.name = "existing_user"
    existing_code.code = "1234"
    existing_code.access_code_id = "id1"
    existing_code.disabled = False
    existing_code.notify_on_use = True
    existing_code.schedule = None
    mock_lock.access_codes = {"id1": existing_code}

    start = dt_datetime(2025, 3, 1, 0, 0)
    end = dt_datetime(2025, 9, 30, 23, 59)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "access_code_id": "id1",
            "start_datetime": start,
            "end_datetime": end,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert isinstance(existing_code.schedule, TemporarySchedule)
    assert existing_code.schedule.start == dt_util.as_utc(start)
    assert existing_code.schedule.end == dt_util.as_utc(end)
    existing_code.save.assert_called_once()


async def test_update_code_service_one_date_only_raises(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test update_code raises when only one date is provided."""
    existing_code = Mock()
    existing_code.name = "existing_user"
    existing_code.code = "1234"
    existing_code.access_code_id = "id1"
    existing_code.schedule = None
    mock_lock.access_codes = {"id1": existing_code}

    with pytest.raises(
        ServiceValidationError,
        match="Start and end times are required together",
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "access_code_id": "id1",
                "end_datetime": dt_datetime(2025, 9, 30),
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_temporary_dates_required"


async def test_update_code_succeeds_despite_notification_error(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test update_code succeeds when save raises but device confirmed the change."""
    existing_code = Mock()
    existing_code.name = "existing_user"
    existing_code.code = "1234"
    existing_code.access_code_id = "id1"
    existing_code.disabled = False
    existing_code.notify_on_use = True
    existing_code.schedule = None
    mock_lock.access_codes = {"id1": existing_code}

    existing_code.save.side_effect = SchlageError("notification failed")

    # After refresh, return updated code confirming the change took effect.
    # Only apply on the second call (the first call is the initial fetch).
    updated_code = Mock()
    updated_code.name = "updated_user"
    updated_code.code = "5678"
    updated_code.access_code_id = "id1"
    updated_code.disabled = True
    updated_code.notify_on_use = False
    updated_code.schedule = None

    call_count = 0

    def refresh_side_effect() -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            mock_lock.access_codes = {"id1": updated_code}

    mock_lock.refresh_access_codes.side_effect = refresh_side_effect

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "access_code_id": "id1",
            "name": "updated_user",
            "code": "5678",
            "notify_on_use": False,
            "disabled": True,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    existing_code.save.assert_called_once()
    assert mock_lock.refresh_access_codes.call_count == 2


async def test_update_code_fails_when_change_not_confirmed(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test update_code raises HomeAssistantError when save fails and change is not confirmed."""
    existing_code = Mock()
    existing_code.name = "existing_user"
    existing_code.code = "1234"
    existing_code.access_code_id = "id1"
    existing_code.disabled = False
    existing_code.notify_on_use = True
    existing_code.schedule = None
    mock_lock.access_codes = {"id1": existing_code}

    existing_code.save.side_effect = SchlageError("API error")

    # After refresh, return unchanged code (device did not apply the change).
    # Only apply on the second call (the first call is the initial fetch).
    unchanged_code = Mock()
    unchanged_code.name = "existing_user"
    unchanged_code.code = "1234"
    unchanged_code.access_code_id = "id1"
    unchanged_code.disabled = False
    unchanged_code.notify_on_use = True
    unchanged_code.schedule = None

    call_count = 0

    def refresh_side_effect() -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            mock_lock.access_codes = {"id1": unchanged_code}

    mock_lock.refresh_access_codes.side_effect = refresh_side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "access_code_id": "id1",
                "name": "updated_user",
                "code": "5678",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_update_code_failed"
    existing_code.save.assert_called_once()
    assert mock_lock.refresh_access_codes.call_count == 2


async def test_add_code_service_refresh_error(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code service raises HomeAssistantError on refresh failure."""
    mock_lock.refresh_access_codes.side_effect = SchlageError("API error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": "1234",
                "notify_on_use": False,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_refresh_failed"


async def test_add_code_service_api_error(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code service raises HomeAssistantError on add failure."""
    mock_lock.access_codes = {}
    mock_lock.add_access_code.side_effect = SchlageError("API error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": "1234",
                "notify_on_use": False,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_add_code_failed"


async def test_delete_code_service_api_error(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test delete_code service raises HomeAssistantError on delete failure."""
    existing_code = Mock()
    existing_code.name = "test_user"
    existing_code.delete.side_effect = SchlageError("API error")
    mock_lock.access_codes = {"1": existing_code}

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_delete_code_failed"


async def test_get_codes_service_refresh_error(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test get_codes service raises HomeAssistantError on refresh failure."""
    mock_lock.refresh_access_codes.side_effect = SchlageError("API error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_CODES,
            service_data={
                "entity_id": "lock.vault_door",
            },
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "schlage_refresh_failed"


async def test_add_code_naive_datetimes_become_utc(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code normalizes naive datetimes to UTC-aware in the schedule."""
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    # Set default time zone to America/New_York (UTC-5 in Jan)
    await hass.config.async_set_time_zone("America/New_York")

    naive_start = dt_datetime(2025, 1, 15, 10, 0)  # 10:00 ET = 15:00 UTC
    naive_end = dt_datetime(2025, 1, 15, 12, 0)  # 12:00 ET = 17:00 UTC

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
            "code": "1234",
            "start_datetime": naive_start,
            "end_datetime": naive_end,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args, AccessCode)
    assert isinstance(call_args.schedule, TemporarySchedule)
    assert call_args.schedule.start.tzinfo is not None
    assert call_args.schedule.start.utcoffset().total_seconds() == 0
    assert call_args.schedule.end.tzinfo is not None
    assert call_args.schedule.end.utcoffset().total_seconds() == 0
    # Verify correct UTC instant for 10:00 ET = 15:00 UTC
    expected_start = dt_util.as_utc(dt_datetime(2025, 1, 15, 15, 0, tzinfo=dt_util.UTC))
    expected_end = dt_util.as_utc(dt_datetime(2025, 1, 15, 17, 0, tzinfo=dt_util.UTC))
    assert call_args.schedule.start == expected_start
    assert call_args.schedule.end == expected_end


async def test_add_code_aware_datetimes_accepted(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code accepts UTC-aware datetimes without double-conversion."""
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    aware_start = dt_util.as_utc(dt_datetime(2025, 6, 1, 8, 0))
    aware_end = dt_util.as_utc(dt_datetime(2025, 6, 1, 10, 0))

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "test_user",
            "code": "1234",
            "start_datetime": aware_start,
            "end_datetime": aware_end,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args.schedule, TemporarySchedule)
    # No double-conversion: the instant must be identical
    assert call_args.schedule.start == aware_start
    assert call_args.schedule.end == aware_end


async def test_build_schedule_start_after_end_utc_aware(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test start > end validation still raises after UTC normalization."""
    mock_lock.access_codes = {}

    # start is 2h after end in the same day — after normalization the relation holds
    start = dt_util.as_utc(dt_datetime(2025, 7, 1, 14, 0))
    end = dt_util.as_utc(dt_datetime(2025, 7, 1, 12, 0))

    with pytest.raises(
        ServiceValidationError,
        match="Start time must be before end time",
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": "1234",
                "start_datetime": start,
                "end_datetime": end,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_start_after_end"


async def test_update_code_comparison_with_aware_schedule(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test update_code with an already-aware schedule from the API does not raise TypeError."""
    aware_start = dt_util.as_utc(dt_datetime(2025, 5, 1, 9, 0))
    aware_end = dt_util.as_utc(dt_datetime(2025, 5, 1, 17, 0))
    existing_code = Mock()
    existing_code.name = "existing_user"
    existing_code.code = "1234"
    existing_code.access_code_id = "id1"
    existing_code.disabled = False
    existing_code.notify_on_use = True
    existing_code.schedule = TemporarySchedule(start=aware_start, end=aware_end)
    mock_lock.access_codes = {"id1": existing_code}

    # Update with new dates — should not raise TypeError during comparison
    new_start = dt_util.as_utc(dt_datetime(2025, 6, 1, 8, 0))
    new_end = dt_util.as_utc(dt_datetime(2025, 6, 1, 18, 0))
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "access_code_id": "id1",
            "start_datetime": new_start,
            "end_datetime": new_end,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert isinstance(existing_code.schedule, TemporarySchedule)
    assert existing_code.schedule.start == new_start
    assert existing_code.schedule.end == new_end
    existing_code.save.assert_called_once()


async def test_update_code_schedule_fails_save_detected(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test schedule-only update that fails save is correctly reported as failed."""
    old_start = dt_util.as_utc(dt_datetime(2025, 1, 1, 9, 0))
    old_end = dt_util.as_utc(dt_datetime(2025, 1, 1, 17, 0))
    existing_code = Mock()
    existing_code.name = "existing_user"
    existing_code.code = "1234"
    existing_code.access_code_id = "id1"
    existing_code.disabled = False
    existing_code.notify_on_use = True
    existing_code.schedule = TemporarySchedule(start=old_start, end=old_end)
    mock_lock.access_codes = {"id1": existing_code}

    existing_code.save.side_effect = SchlageError("API error")

    # After refresh, return code with the OLD schedule (change was NOT applied).
    old_schedule_code = Mock()
    old_schedule_code.name = "existing_user"
    old_schedule_code.code = "1234"
    old_schedule_code.access_code_id = "id1"
    old_schedule_code.disabled = False
    old_schedule_code.notify_on_use = True
    old_schedule_code.schedule = TemporarySchedule(start=old_start, end=old_end)

    call_count = 0

    def refresh_side_effect() -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            mock_lock.access_codes = {"id1": old_schedule_code}

    mock_lock.refresh_access_codes.side_effect = refresh_side_effect

    new_start = dt_util.as_utc(dt_datetime(2025, 6, 1, 8, 0))
    new_end = dt_util.as_utc(dt_datetime(2025, 6, 1, 18, 0))

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "access_code_id": "id1",
                "start_datetime": new_start,
                "end_datetime": new_end,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_update_code_failed"
    existing_code.save.assert_called_once()
    assert mock_lock.refresh_access_codes.call_count == 2


async def test_update_code_schedule_succeeds_despite_notification_error(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test schedule update succeeds when save raises but device confirmed the change."""
    old_start = dt_util.as_utc(dt_datetime(2025, 1, 1, 9, 0))
    old_end = dt_util.as_utc(dt_datetime(2025, 1, 1, 17, 0))
    existing_code = Mock()
    existing_code.name = "existing_user"
    existing_code.code = "1234"
    existing_code.access_code_id = "id1"
    existing_code.disabled = False
    existing_code.notify_on_use = True
    existing_code.schedule = TemporarySchedule(start=old_start, end=old_end)
    mock_lock.access_codes = {"id1": existing_code}

    existing_code.save.side_effect = SchlageError("notification failed")

    # After refresh, return code with the NEW schedule (change was applied).
    new_start = dt_util.as_utc(dt_datetime(2025, 6, 1, 8, 0))
    new_end = dt_util.as_utc(dt_datetime(2025, 6, 1, 18, 0))
    updated_code = Mock()
    updated_code.name = "existing_user"
    updated_code.code = "1234"
    updated_code.access_code_id = "id1"
    updated_code.disabled = False
    updated_code.notify_on_use = True
    updated_code.schedule = TemporarySchedule(start=new_start, end=new_end)

    call_count = 0

    def refresh_side_effect() -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            mock_lock.access_codes = {"id1": updated_code}

    mock_lock.refresh_access_codes.side_effect = refresh_side_effect

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "access_code_id": "id1",
            "start_datetime": new_start,
            "end_datetime": new_end,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    existing_code.save.assert_called_once()
    assert mock_lock.refresh_access_codes.call_count == 2


async def test_update_code_rejects_duplicate_name(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test update_code rejects name that matches another code (case-insensitive)."""
    target_code = Mock()
    target_code.name = "target_user"
    target_code.code = "1234"
    target_code.access_code_id = "id_target"
    target_code.disabled = False
    target_code.notify_on_use = True
    target_code.schedule = None

    other_code = Mock()
    other_code.name = "Existing_User"
    other_code.code = "5678"
    other_code.access_code_id = "id_other"

    mock_lock.access_codes = {
        "id_target": target_code,
        "id_other": other_code,
    }

    with pytest.raises(
        ServiceValidationError,
        match='A PIN code with the name "existing_user" already exists on the lock',
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "access_code_id": "id_target",
                "name": "existing_user",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_name_exists"


async def test_update_code_rejects_duplicate_pin(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test update_code rejects PIN that matches another code."""
    target_code = Mock()
    target_code.name = "target_user"
    target_code.code = "1234"
    target_code.access_code_id = "id_target"
    target_code.disabled = False
    target_code.notify_on_use = True
    target_code.schedule = None

    other_code = Mock()
    other_code.name = "other_user"
    other_code.code = "9999"
    other_code.access_code_id = "id_other"

    mock_lock.access_codes = {
        "id_target": target_code,
        "id_other": other_code,
    }

    with pytest.raises(
        ServiceValidationError,
        match="A PIN code with this value already exists on the lock",
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "access_code_id": "id_target",
                "code": "9999",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_code_exists"


async def test_update_code_allows_same_name_and_code(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test update_code allows keeping same name/code on the target code."""
    target_code = Mock()
    target_code.name = "user1"
    target_code.code = "1234"
    target_code.access_code_id = "id1"
    target_code.disabled = False
    target_code.notify_on_use = True
    target_code.schedule = None

    other_code = Mock()
    other_code.name = "user2"
    other_code.code = "5678"
    other_code.access_code_id = "id2"

    mock_lock.access_codes = {
        "id1": target_code,
        "id2": other_code,
    }

    # Updating name to same value should not raise.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "access_code_id": "id1",
            "name": "user1",
            "code": "1234",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    target_code.save.assert_called_once()


async def test_delete_code_service_by_access_code_id(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test delete_code service using access_code_id."""
    existing_code = Mock()
    existing_code.name = "test_user"
    existing_code.delete = Mock()
    mock_lock.access_codes = {"abc123": existing_code}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "access_code_id": "abc123",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    existing_code.delete.assert_called_once()
    mock_lock.refresh_access_codes.assert_called_once()


async def test_delete_code_service_ambiguous_identifiers_raises(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test delete_code raises when both name and access_code_id are provided."""
    mock_lock.access_codes = {}

    with pytest.raises(
        ServiceValidationError,
        match="Provide either name or access_code_id, not both",
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "access_code_id": "abc123",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_delete_code_ambiguous"


async def test_get_codes_service_recurring_schedule(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test get_codes returns type=recurring when code has a RecurringSchedule."""
    schedule = RecurringSchedule(
        days_of_week=RecurringSchedule.__dataclass_fields__[
            "days_of_week"
        ].default_factory(),
        start_hour=8,
        start_minute=0,
        end_hour=18,
        end_minute=0,
    )
    code = Mock()
    code.name = "recurring_user"
    code.code = "2222"
    code.access_code_id = "id_recurring"
    code.disabled = False
    code.notify_on_use = True
    code.schedule = schedule
    mock_lock.access_codes = {"1": code}

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_CODES,
        service_data={
            "entity_id": "lock.vault_door",
        },
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    schedule_resp = response["lock.vault_door"]["1"]["schedule"]
    assert schedule_resp["type"] == "recurring"
    assert "days_of_week" in schedule_resp
    assert schedule_resp["start_hour"] == 8
    assert schedule_resp["start_minute"] == 0
    assert schedule_resp["end_hour"] == 18
    assert schedule_resp["end_minute"] == 0


async def test_get_codes_service_multi_recurring_schedule(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test get_codes returns type=recurring_multi when code has a MultiRecurringSchedule."""
    schedule1 = RecurringSchedule(
        days_of_week=RecurringSchedule.__dataclass_fields__[
            "days_of_week"
        ].default_factory(),
        start_hour=6,
        start_minute=0,
        end_hour=12,
        end_minute=0,
    )
    schedule2 = RecurringSchedule(
        days_of_week=RecurringSchedule.__dataclass_fields__[
            "days_of_week"
        ].default_factory(),
        start_hour=14,
        start_minute=0,
        end_hour=20,
        end_minute=0,
    )
    multi_schedule = MultiRecurringSchedule(schedule1=schedule1, schedule2=schedule2)
    code = Mock()
    code.name = "multi_user"
    code.code = "3333"
    code.access_code_id = "id_multi"
    code.disabled = False
    code.notify_on_use = True
    code.schedule = multi_schedule
    mock_lock.access_codes = {"1": code}

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_CODES,
        service_data={
            "entity_id": "lock.vault_door",
        },
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    schedule_resp = response["lock.vault_door"]["1"]["schedule"]
    assert schedule_resp["type"] == "recurring_multi"
    assert "windows" in schedule_resp
    assert len(schedule_resp["windows"]) == 2
    assert schedule_resp["windows"][0]["start_hour"] == 6
    assert schedule_resp["windows"][0]["end_hour"] == 12
    assert schedule_resp["windows"][1]["start_hour"] == 14
    assert schedule_resp["windows"][1]["end_hour"] == 20
