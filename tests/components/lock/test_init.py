"""The tests for the lock component."""
from __future__ import annotations

from typing import Any

import pytest

from homeassistant.components.lock import (
    ATTR_CODE,
    CONF_DEFAULT_CODE,
    DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
    LockEntityFeature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from tests.testing_config.custom_components.test.lock import MockLock

TEST_LOCK_ENTITY_ID = "lock.test_lock"


async def help_test_async_lock_service(
    hass: HomeAssistant, service: str, code: str | None | UndefinedType = UNDEFINED
) -> None:
    """Help to lock a test lock."""
    data: dict[str, Any] = {"entity_id": TEST_LOCK_ENTITY_ID}
    if code is not UNDEFINED:
        data[ATTR_CODE] = code

    await hass.services.async_call(DOMAIN, service, data, blocking=True)


async def test_lock_default(hass: HomeAssistant, mock_lock_entity: MockLock) -> None:
    """Test lock entity with defaults."""

    assert mock_lock_entity.code_format is None
    assert mock_lock_entity.state is None


async def test_lock_states(hass: HomeAssistant, mock_lock_entity: MockLock) -> None:
    """Test lock entity states."""

    assert mock_lock_entity.state is None

    mock_lock_entity._attr_is_locking = True
    assert mock_lock_entity.is_locking
    assert mock_lock_entity.state == STATE_LOCKING

    await help_test_async_lock_service(hass, SERVICE_LOCK)
    assert mock_lock_entity.is_locked
    assert mock_lock_entity.state == STATE_LOCKED

    mock_lock_entity._attr_is_unlocking = True
    assert mock_lock_entity.is_unlocking
    assert mock_lock_entity.state == STATE_UNLOCKING

    await help_test_async_lock_service(hass, SERVICE_UNLOCK)
    assert not mock_lock_entity.is_locked
    assert mock_lock_entity.state == STATE_UNLOCKED

    mock_lock_entity._attr_is_jammed = True
    assert mock_lock_entity.is_jammed
    assert mock_lock_entity.state == STATE_JAMMED
    assert not mock_lock_entity.is_locked


@pytest.mark.parametrize(
    ("default_code", "code_format", "supported_features"),
    [("1234", r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_set_mock_lock_options(
    hass: HomeAssistant,
    mock_lock_entity: MockLock,
) -> None:
    """Test mock attributes and default code stored in the registry."""

    assert mock_lock_entity._lock_option_default_code == "1234"
    state = hass.states.get(TEST_LOCK_ENTITY_ID)
    assert state is not None
    assert state.attributes["code_format"] == r"^\d{4}$"
    assert state.attributes["supported_features"] == LockEntityFeature.OPEN


@pytest.mark.parametrize(("default_code", "code_format"), [("1234", r"^\d{4}$")])
async def test_default_code_option_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lock_entity: MockLock,
) -> None:
    """Test default code stored in the registry is updated."""

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
    state = hass.states.get(TEST_LOCK_ENTITY_ID)
    assert state.attributes["code_format"] == r"^\d{4}$"

    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_OPEN)
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_OPEN, code="")
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_OPEN, code="HELLO")
    await help_test_async_lock_service(hass, SERVICE_OPEN, code="1234")
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
    state = hass.states.get(TEST_LOCK_ENTITY_ID)
    assert state.attributes["code_format"] == r"^\d{4}$"

    await help_test_async_lock_service(hass, SERVICE_UNLOCK, code="1234")
    mock_lock_entity.calls_unlock.assert_called_with(code="1234")
    assert mock_lock_entity.calls_lock.call_count == 0

    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_LOCK)
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_LOCK, code="")
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_LOCK, code="HELLO")
    await help_test_async_lock_service(hass, SERVICE_LOCK, code="1234")
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
    state = hass.states.get(TEST_LOCK_ENTITY_ID)
    assert state.attributes["code_format"] == r"^\d{4}$"

    await help_test_async_lock_service(hass, SERVICE_LOCK, code="1234")
    mock_lock_entity.calls_lock.assert_called_with(code="1234")
    assert mock_lock_entity.calls_unlock.call_count == 0

    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_UNLOCK)
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_UNLOCK, code="")
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_UNLOCK, code="HELLO")
    await help_test_async_lock_service(hass, SERVICE_UNLOCK, code="1234")
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

    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_OPEN, code="123456")
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_LOCK, code="123456")
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_UNLOCK, code="123456")


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(None, LockEntityFeature.OPEN)],
)
async def test_lock_with_no_code(
    hass: HomeAssistant, mock_lock_entity: MockLock
) -> None:
    """Test lock entity without code."""
    await help_test_async_lock_service(hass, SERVICE_OPEN)
    mock_lock_entity.calls_open.assert_called_with()
    await help_test_async_lock_service(hass, SERVICE_LOCK)
    mock_lock_entity.calls_lock.assert_called_with()
    await help_test_async_lock_service(hass, SERVICE_UNLOCK)
    mock_lock_entity.calls_unlock.assert_called_with()

    mock_lock_entity.calls_open.reset_mock()
    mock_lock_entity.calls_lock.reset_mock()
    mock_lock_entity.calls_unlock.reset_mock()

    await help_test_async_lock_service(hass, SERVICE_OPEN, code="")
    mock_lock_entity.calls_open.assert_called_with()
    await help_test_async_lock_service(hass, SERVICE_LOCK, code="")
    mock_lock_entity.calls_lock.assert_called_with()
    await help_test_async_lock_service(hass, SERVICE_UNLOCK, code="")
    mock_lock_entity.calls_unlock.assert_called_with()


@pytest.mark.parametrize(
    ("default_code", "code_format", "supported_features"),
    [("1234", r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_lock_with_default_code(
    hass: HomeAssistant, mock_lock_entity: MockLock
) -> None:
    """Test lock entity with default code."""

    assert mock_lock_entity.state_attributes == {"code_format": r"^\d{4}$"}
    assert mock_lock_entity._lock_option_default_code == "1234"

    await help_test_async_lock_service(hass, SERVICE_OPEN, code="1234")
    mock_lock_entity.calls_open.assert_called_with(code="1234")
    await help_test_async_lock_service(hass, SERVICE_LOCK, code="1234")
    mock_lock_entity.calls_lock.assert_called_with(code="1234")
    await help_test_async_lock_service(hass, SERVICE_UNLOCK, code="1234")
    mock_lock_entity.calls_unlock.assert_called_with(code="1234")

    mock_lock_entity.calls_open.reset_mock()
    mock_lock_entity.calls_lock.reset_mock()
    mock_lock_entity.calls_unlock.reset_mock()

    await help_test_async_lock_service(hass, SERVICE_OPEN, code="")
    mock_lock_entity.calls_open.assert_called_with(code="1234")
    await help_test_async_lock_service(hass, SERVICE_LOCK, code="")
    mock_lock_entity.calls_lock.assert_called_with(code="1234")
    await help_test_async_lock_service(hass, SERVICE_UNLOCK, code="")
    mock_lock_entity.calls_unlock.assert_called_with(code="1234")


@pytest.mark.parametrize(
    ("default_code", "code_format", "supported_features"),
    [("123456", r"^\d{4}$", LockEntityFeature.OPEN)],
)
async def test_lock_with_illegal_default_code(
    hass: HomeAssistant, mock_lock_entity: MockLock
) -> None:
    """Test lock entity with illegal default code."""
    assert mock_lock_entity.state_attributes == {"code_format": r"^\d{4}$"}
    assert mock_lock_entity._lock_option_default_code == ""

    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_OPEN)
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_LOCK)
    with pytest.raises(ValueError):
        await help_test_async_lock_service(hass, SERVICE_UNLOCK)
