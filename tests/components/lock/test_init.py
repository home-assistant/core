"""The tests for the lock component."""

from __future__ import annotations

from enum import Enum
import re
from typing import Any

import pytest

from homeassistant.components import lock
from homeassistant.components.lock import (
    ATTR_CODE,
    CONF_DEFAULT_CODE,
    DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    LockEntityFeature,
    LockState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .conftest import MockLock

from tests.common import help_test_all, import_and_test_deprecated_constant_enum


async def help_test_async_lock_service(
    hass: HomeAssistant,
    entity_id: str,
    service: str,
    code: str | None | UndefinedType = UNDEFINED,
) -> None:
    """Help to lock a test lock."""
    data: dict[str, Any] = {"entity_id": entity_id}
    if code is not UNDEFINED:
        data[ATTR_CODE] = code

    await hass.services.async_call(DOMAIN, service, data, blocking=True)


async def test_lock_default(hass: HomeAssistant, mock_lock_entity: MockLock) -> None:
    """Test lock entity with defaults."""

    assert mock_lock_entity.code_format is None
    assert mock_lock_entity.state is None
    assert mock_lock_entity.is_jammed is None
    assert mock_lock_entity.is_locked is None
    assert mock_lock_entity.is_locking is None
    assert mock_lock_entity.is_unlocking is None
    assert mock_lock_entity.is_opening is None
    assert mock_lock_entity.is_open is None


async def test_lock_states(hass: HomeAssistant, mock_lock_entity: MockLock) -> None:
    """Test lock entity states."""

    assert mock_lock_entity.state is None

    mock_lock_entity._attr_is_locking = True
    assert mock_lock_entity.is_locking
    assert mock_lock_entity.state == LockState.LOCKING

    mock_lock_entity._attr_is_locked = True
    mock_lock_entity._attr_is_locking = False
    assert mock_lock_entity.is_locked
    assert mock_lock_entity.state == LockState.LOCKED

    mock_lock_entity._attr_is_unlocking = True
    assert mock_lock_entity.is_unlocking
    assert mock_lock_entity.state == LockState.UNLOCKING

    mock_lock_entity._attr_is_locked = False
    mock_lock_entity._attr_is_unlocking = False
    assert not mock_lock_entity.is_locked
    assert mock_lock_entity.state == LockState.UNLOCKED

    mock_lock_entity._attr_is_jammed = True
    assert mock_lock_entity.is_jammed
    assert mock_lock_entity.state == LockState.JAMMED
    assert not mock_lock_entity.is_locked

    mock_lock_entity._attr_is_jammed = False
    mock_lock_entity._attr_is_opening = True
    assert mock_lock_entity.is_opening
    assert mock_lock_entity.state == LockState.OPENING
    assert mock_lock_entity.is_opening

    mock_lock_entity._attr_is_opening = False
    mock_lock_entity._attr_is_open = True
    assert not mock_lock_entity.is_opening
    assert mock_lock_entity.state == LockState.OPEN
    assert not mock_lock_entity.is_opening
    assert mock_lock_entity.is_open


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_set_mock_lock_options(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lock_entity: MockLock,
) -> None:
    """Test mock attributes and default code stored in the registry."""
    entity_registry.async_update_entity_options(
        "lock.test_lock", "lock", {CONF_DEFAULT_CODE: "1234"}
    )
    await hass.async_block_till_done()

    assert mock_lock_entity._lock_option_default_code == "1234"
    state = hass.states.get(mock_lock_entity.entity_id)
    assert state is not None
    assert state.attributes["code_format"] == r"^\d{4}$"
    assert state.attributes["supported_features"] == LockEntityFeature.OPEN


@pytest.mark.parametrize("code_format", [r"^\d{4}$"])
async def test_default_code_option_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lock_entity: MockLock,
) -> None:
    """Test default code stored in the registry is updated."""

    assert mock_lock_entity._lock_option_default_code == ""

    entity_registry.async_update_entity_options(
        "lock.test_lock", "lock", {CONF_DEFAULT_CODE: "4321"}
    )
    await hass.async_block_till_done()

    assert mock_lock_entity._lock_option_default_code == "4321"


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_lock_open_with_code(
    hass: HomeAssistant, mock_lock_entity: MockLock
) -> None:
    """Test lock entity with open service."""
    state = hass.states.get(mock_lock_entity.entity_id)
    assert state.attributes["code_format"] == r"^\d{4}$"

    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_OPEN
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_OPEN, code=""
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_OPEN, code="HELLO"
        )
    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_OPEN, code="1234"
    )
    assert mock_lock_entity.calls_open.call_count == 1
    mock_lock_entity.calls_open.assert_called_with(code="1234")


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_lock_lock_with_code(
    hass: HomeAssistant, mock_lock_entity: MockLock
) -> None:
    """Test lock entity with open service."""
    state = hass.states.get(mock_lock_entity.entity_id)
    assert state.attributes["code_format"] == r"^\d{4}$"

    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_UNLOCK, code="1234"
    )
    mock_lock_entity.calls_unlock.assert_called_with(code="1234")
    assert mock_lock_entity.calls_lock.call_count == 0

    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_LOCK
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_LOCK, code=""
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_LOCK, code="HELLO"
        )
    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_LOCK, code="1234"
    )
    assert mock_lock_entity.calls_lock.call_count == 1
    mock_lock_entity.calls_lock.assert_called_with(code="1234")


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_lock_unlock_with_code(
    hass: HomeAssistant, mock_lock_entity: MockLock
) -> None:
    """Test unlock entity with open service."""
    state = hass.states.get(mock_lock_entity.entity_id)
    assert state.attributes["code_format"] == r"^\d{4}$"

    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_LOCK, code="1234"
    )
    mock_lock_entity.calls_lock.assert_called_with(code="1234")
    assert mock_lock_entity.calls_unlock.call_count == 0

    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_UNLOCK
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_UNLOCK, code=""
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_UNLOCK, code="HELLO"
        )
    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_UNLOCK, code="1234"
    )
    assert mock_lock_entity.calls_unlock.call_count == 1
    mock_lock_entity.calls_unlock.assert_called_with(code="1234")


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_lock_with_illegal_code(
    hass: HomeAssistant, mock_lock_entity: MockLock
) -> None:
    """Test lock entity with default code that does not match the code format."""

    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_OPEN, code="123456"
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_LOCK, code="123456"
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_UNLOCK, code="123456"
        )


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(None, LockEntityFeature.OPEN)],
)
async def test_lock_with_no_code(
    hass: HomeAssistant, mock_lock_entity: MockLock
) -> None:
    """Test lock entity without code."""
    await help_test_async_lock_service(hass, mock_lock_entity.entity_id, SERVICE_OPEN)
    mock_lock_entity.calls_open.assert_called_with()
    await help_test_async_lock_service(hass, mock_lock_entity.entity_id, SERVICE_LOCK)
    mock_lock_entity.calls_lock.assert_called_with()
    await help_test_async_lock_service(hass, mock_lock_entity.entity_id, SERVICE_UNLOCK)
    mock_lock_entity.calls_unlock.assert_called_with()

    mock_lock_entity.calls_open.reset_mock()
    mock_lock_entity.calls_lock.reset_mock()
    mock_lock_entity.calls_unlock.reset_mock()

    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_OPEN, code=""
    )
    mock_lock_entity.calls_open.assert_called_with()
    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_LOCK, code=""
    )
    mock_lock_entity.calls_lock.assert_called_with()
    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_UNLOCK, code=""
    )
    mock_lock_entity.calls_unlock.assert_called_with()


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_lock_with_default_code(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_lock_entity: MockLock
) -> None:
    """Test lock entity with default code."""
    entity_registry.async_update_entity_options(
        "lock.test_lock", "lock", {CONF_DEFAULT_CODE: "1234"}
    )
    await hass.async_block_till_done()

    assert mock_lock_entity.state_attributes == {"code_format": r"^\d{4}$"}
    assert mock_lock_entity._lock_option_default_code == "1234"

    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_OPEN, code="1234"
    )
    mock_lock_entity.calls_open.assert_called_with(code="1234")
    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_LOCK, code="1234"
    )
    mock_lock_entity.calls_lock.assert_called_with(code="1234")
    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_UNLOCK, code="1234"
    )
    mock_lock_entity.calls_unlock.assert_called_with(code="1234")

    mock_lock_entity.calls_open.reset_mock()
    mock_lock_entity.calls_lock.reset_mock()
    mock_lock_entity.calls_unlock.reset_mock()

    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_OPEN, code=""
    )
    mock_lock_entity.calls_open.assert_called_with(code="1234")
    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_LOCK, code=""
    )
    mock_lock_entity.calls_lock.assert_called_with(code="1234")
    await help_test_async_lock_service(
        hass, mock_lock_entity.entity_id, SERVICE_UNLOCK, code=""
    )
    mock_lock_entity.calls_unlock.assert_called_with(code="1234")


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_lock_with_illegal_default_code(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_lock_entity: MockLock
) -> None:
    """Test lock entity with illegal default code."""
    entity_registry.async_update_entity_options(
        "lock.test_lock", "lock", {CONF_DEFAULT_CODE: "123456"}
    )
    await hass.async_block_till_done()

    assert mock_lock_entity.state_attributes == {"code_format": r"^\d{4}$"}
    assert mock_lock_entity._lock_option_default_code == ""

    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_OPEN
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_LOCK
        )
    with pytest.raises(
        ServiceValidationError,
        match=re.escape(
            rf"The code for lock.test_lock doesn't match pattern ^\d{{{4}}}$"
        ),
    ) as exc:
        await help_test_async_lock_service(
            hass, mock_lock_entity.entity_id, SERVICE_UNLOCK
        )

    assert (
        str(exc.value)
        == rf"The code for lock.test_lock doesn't match pattern ^\d{{{4}}}$"
    )
    assert exc.value.translation_key == "add_default_code"


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(lock)


def _create_tuples(
    enum: type[Enum], constant_prefix: str, remove_in_version: str
) -> list[tuple[Enum, str]]:
    return [
        (enum_field, constant_prefix, remove_in_version)
        for enum_field in enum
        if enum_field
        not in [
            lock.LockState.OPEN,
            lock.LockState.OPENING,
        ]
    ]


@pytest.mark.parametrize(
    ("enum", "constant_prefix", "remove_in_version"),
    _create_tuples(lock.LockEntityFeature, "SUPPORT_", "2025.1")
    + _create_tuples(lock.LockState, "STATE_", "2025.10"),
)
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: Enum,
    constant_prefix: str,
    remove_in_version: str,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, lock, enum, constant_prefix, remove_in_version
    )


def test_deprecated_supported_features_ints(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated supported features ints."""

    class MockLockEntity(lock.LockEntity):
        _attr_supported_features = 1

    entity = MockLockEntity()
    assert entity.supported_features is lock.LockEntityFeature(1)
    assert "MockLockEntity" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "LockEntityFeature.OPEN" in caplog.text
    caplog.clear()
    assert entity.supported_features is lock.LockEntityFeature(1)
    assert "is using deprecated supported features values" not in caplog.text
