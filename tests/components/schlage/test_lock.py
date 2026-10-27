"""Test schlage lock."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import probatio
from pyschlage.code import (
    AccessCode,
    DaysOfWeek,
    MultiRecurringSchedule,
    RecurringSchedule,
    TemporarySchedule,
)
from pyschlage.exceptions import Error as SchlageError
import pytest
from pytest_homeassistant.common import async_fire_time_changed, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.components.schlage.const import (
    DOMAIN,
    SERVICE_ADD_CODE,
    SERVICE_DELETE_CODE,
    SERVICE_GET_CODES,
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

from . import MockSchlageConfigEntry


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

    with pytest.raises(probatio.Invalid):
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


async def test_get_codes_service(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test get_codes service."""
    # Mock existing access codes without a schedule
    code1 = Mock()
    code1.name = "user1"
    code1.code = "1234"
    code1.access_code_id = "ac_001"
    code1.schedule = None
    code2 = Mock()
    code2.name = "user2"
    code2.code = "5678"
    code2.access_code_id = "ac_002"
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
                "access_code_id": "ac_001",
                "schedule": None,
            },
            "2": {
                "name": "user2",
                "code": "5678",
                "access_code_id": "ac_002",
                "schedule": None,
            },
        }
    }


_WEEKDAY_DAYS = DaysOfWeek(
    sun=False, mon=True, tue=False, wed=True, thu=False, fri=True, sat=False
)
_EXPECTED_WEEKDAY_DAYS = {
    "sun": False,
    "mon": True,
    "tue": False,
    "wed": True,
    "thu": False,
    "fri": True,
    "sat": False,
}

_WEEKEND_DAYS = DaysOfWeek(
    sun=True, mon=False, tue=False, wed=False, thu=False, fri=False, sat=True
)
_EXPECTED_WEEKEND_DAYS = {
    "sun": True,
    "mon": False,
    "tue": False,
    "wed": False,
    "thu": False,
    "fri": False,
    "sat": True,
}

_MORNING_WINDOW = RecurringSchedule(
    days_of_week=_WEEKDAY_DAYS,
    start_hour=8,
    start_minute=5,
    end_hour=18,
    end_minute=30,
)

_EVENING_WINDOW = RecurringSchedule(
    days_of_week=_WEEKEND_DAYS,
    start_hour=20,
    start_minute=0,
    end_hour=22,
    end_minute=45,
)

_EXPECTED_MORNING_WINDOW = {
    "days_of_week": _EXPECTED_WEEKDAY_DAYS,
    "start_time": "08:05:00",
    "end_time": "18:30:00",
}

_EXPECTED_EVENING_WINDOW = {
    "days_of_week": _EXPECTED_WEEKEND_DAYS,
    "start_time": "20:00:00",
    "end_time": "22:45:00",
}

_TEMPORARY_START = datetime(2025, 1, 1, 8, 0, 0, tzinfo=UTC)
_TEMPORARY_END = datetime(2025, 1, 1, 18, 0, 0, tzinfo=UTC)
_LATER_TEMPORARY_START = datetime(2025, 1, 2, 8, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("schedule", "expected_schedule"),
    [
        pytest.param(
            _MORNING_WINDOW,
            {"type": "recurring", **_EXPECTED_MORNING_WINDOW},
            id="recurring",
        ),
        pytest.param(
            MultiRecurringSchedule(_MORNING_WINDOW, _EVENING_WINDOW),
            {
                "type": "multi_recurring",
                "windows": [_EXPECTED_MORNING_WINDOW, _EXPECTED_EVENING_WINDOW],
            },
            id="multi-recurring-two-windows",
        ),
        pytest.param(
            MultiRecurringSchedule(_MORNING_WINDOW, None),
            {"type": "multi_recurring", "windows": [_EXPECTED_MORNING_WINDOW]},
            id="multi-recurring-one-window",
        ),
    ],
)
async def test_get_codes_service_schedule_time_values(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
    schedule: MultiRecurringSchedule | RecurringSchedule,
    expected_schedule: dict[str, Any],
) -> None:
    """Test get_codes combines recurring hour and minute into time values."""
    mock_lock.access_codes = {
        "1": AccessCode(
            name="user1", code="1234", access_code_id="1", schedule=schedule
        )
    }

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
                "access_code_id": "1",
                "schedule": expected_schedule,
            }
        }
    }


async def test_get_codes_service_temporary_schedule(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test get_codes serializes a temporary schedule through the public action."""
    mock_lock.access_codes = {
        "1": AccessCode(
            name="temp_user",
            code="1234",
            access_code_id="ac_001",
            schedule=TemporarySchedule(start=_TEMPORARY_START, end=_TEMPORARY_END),
        )
    }

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
                "name": "temp_user",
                "code": "1234",
                "access_code_id": "ac_001",
                "schedule": {
                    "type": "temporary",
                    "start_datetime": "2025-01-01T08:00:00+00:00",
                    "end_datetime": "2025-01-01T18:00:00+00:00",
                },
            }
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


async def test_add_code_service_temporary_pin(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code service with both datetimes creates a temporary PIN."""
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "temp_user",
            "code": "1234",
            "notify_on_use": True,
            "start_datetime": _TEMPORARY_START.isoformat(),
            "end_datetime": _TEMPORARY_END.isoformat(),
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args, AccessCode)
    assert call_args.name == "temp_user"
    assert call_args.code == "1234"
    assert isinstance(call_args.schedule, TemporarySchedule)
    assert call_args.schedule.start == _TEMPORARY_START
    assert call_args.schedule.end == _TEMPORARY_END


async def test_add_code_service_validation_before_refresh(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test date validation runs before the access code refresh."""
    mock_lock.refresh_access_codes.side_effect = SchlageError("API error")

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": "1234",
                "start_datetime": _TEMPORARY_START.isoformat(),
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_temporary_dates_required"
    mock_lock.refresh_access_codes.assert_not_called()


@pytest.mark.parametrize(
    ("service_data", "match", "translation_key"),
    [
        pytest.param(
            {"start_datetime": _TEMPORARY_START.isoformat()},
            "Both start and end datetimes must be provided",
            "schlage_temporary_dates_required",
            id="start_without_end",
        ),
        pytest.param(
            {"end_datetime": _TEMPORARY_END.isoformat()},
            "Both start and end datetimes must be provided",
            "schlage_temporary_dates_required",
            id="end_without_start",
        ),
        pytest.param(
            {
                "start_datetime": _LATER_TEMPORARY_START.isoformat(),
                "end_datetime": _TEMPORARY_END.isoformat(),
            },
            "Start datetime must be before end datetime",
            "schlage_start_after_end",
            id="start_after_end",
        ),
        pytest.param(
            {
                "start_datetime": _TEMPORARY_START.isoformat(),
                "end_datetime": _TEMPORARY_START.isoformat(),
            },
            "Start datetime must be before end datetime",
            "schlage_start_after_end",
            id="start_equals_end",
        ),
    ],
)
async def test_add_code_service_invalid_datetime(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
    service_data: dict[str, str],
    match: str,
    translation_key: str,
) -> None:
    """Test add_code service rejects invalid datetime combinations."""
    with pytest.raises(ServiceValidationError, match=match) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CODE,
            service_data={
                "entity_id": "lock.vault_door",
                "name": "test_user",
                "code": "1234",
                **service_data,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key


async def test_add_code_service_temporary_pin_non_utc_timezone(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test add_code service converts naive non UTC datetimes to UTC."""
    await hass.config.async_set_time_zone("America/New_York")
    mock_lock.access_codes = {}
    mock_lock.add_access_code = Mock()

    # September 2026 is EDT (UTC-4), so naive 08:00 is 12:00 UTC and 18:00 is 22:00 UTC.
    start_naive = datetime(2026, 9, 1, 8, 0, 0)
    end_naive = datetime(2026, 9, 1, 18, 0, 0)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CODE,
        service_data={
            "entity_id": "lock.vault_door",
            "name": "temp_user",
            "code": "1234",
            "start_datetime": start_naive.isoformat(),
            "end_datetime": end_naive.isoformat(),
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lock.add_access_code.assert_called_once()
    call_args = mock_lock.add_access_code.call_args[0][0]
    assert isinstance(call_args.schedule, TemporarySchedule)
    assert call_args.schedule.start == datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    assert call_args.schedule.end == datetime(2026, 9, 1, 22, 0, 0, tzinfo=UTC)
