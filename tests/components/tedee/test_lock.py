"""Tests for tedee lock."""
from unittest.mock import MagicMock

from pytedee_async.exception import TedeeClientException
import pytest

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.components.tedee.const import (
    ATTR_CONNECTED,
    ATTR_DURATION_PULLSPRING,
    ATTR_NUMERIC_STATE,
    ATTR_SEMI_LOCKED,
    ATTR_SUPPORT_PULLSPING,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_lock(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the tedee lock."""
    mock_tedee.lock.return_value = None
    mock_tedee.unlock.return_value = None
    mock_tedee.open.return_value = None

    state = hass.states.get("lock.lock_1a2b_lock")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Lock-1A2B Lock"
    assert state.attributes.get(ATTR_ICON) == "mdi:lock"
    assert state.state == STATE_UNLOCKED

    # test extra attributes
    assert state.attributes.get(ATTR_CONNECTED) is True
    assert state.attributes.get(ATTR_DURATION_PULLSPRING) == 2
    assert state.attributes.get(ATTR_NUMERIC_STATE) == 2
    assert state.attributes.get(ATTR_SEMI_LOCKED) is False
    assert state.attributes.get(ATTR_SUPPORT_PULLSPING) is True
    assert state.attributes.get(ATTR_BATTERY_CHARGING) is False

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345-lock"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, 12345)}
    assert device.manufacturer == "tedee"
    assert device.name == "Lock-1A2B"
    assert device.model == "Tedee PRO"

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {
            ATTR_ENTITY_ID: "lock.lock_1a2b_lock",
        },
        blocking=True,
    )

    assert len(mock_tedee.lock.mock_calls) == 1
    mock_tedee.lock.assert_called_once_with(12345)
    state = hass.states.get("lock.lock_1a2b_lock")
    assert state.state == STATE_LOCKING

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {
            ATTR_ENTITY_ID: "lock.lock_1a2b_lock",
        },
        blocking=True,
    )

    assert len(mock_tedee.unlock.mock_calls) == 1
    mock_tedee.unlock.assert_called_once_with(12345)
    state = hass.states.get("lock.lock_1a2b_lock")
    assert state.state == STATE_UNLOCKING

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_OPEN,
        {
            ATTR_ENTITY_ID: "lock.lock_1a2b_lock",
        },
        blocking=True,
    )

    assert len(mock_tedee.open.mock_calls) == 1
    mock_tedee.open.assert_called_once_with(12345)
    state = hass.states.get("lock.lock_1a2b_lock")
    assert state.state == STATE_UNLOCKING


async def test_lock_errors(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
):
    """Test event errors."""
    mock_tedee.lock.side_effect = TedeeClientException("Boom")
    with pytest.raises(HomeAssistantError, match="Failed to lock the door. Lock 12345"):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b_lock",
            },
            blocking=True,
        )

    mock_tedee.unlock.side_effect = TedeeClientException("Boom")
    with pytest.raises(
        HomeAssistantError, match="Failed to unlock the door. Lock 12345"
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b_lock",
            },
            blocking=True,
        )

    mock_tedee.open.side_effect = TedeeClientException("Boom")
    with pytest.raises(
        HomeAssistantError, match="Failed to unlatch the door. Lock 12345"
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_OPEN,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b_lock",
            },
            blocking=True,
        )


async def test_lock_without_pullspring(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the tedee lock without pullspring."""
    mock_tedee.lock.return_value = None
    mock_tedee.unlock.return_value = None
    mock_tedee.open.return_value = None

    state = hass.states.get("lock.lock_2c3d_lock")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Lock-2C3D Lock"
    assert state.attributes.get(ATTR_ICON) == "mdi:lock"
    assert state.state == STATE_UNLOCKED

    # test extra attributes
    assert state.attributes.get(ATTR_CONNECTED) is True
    assert state.attributes.get(ATTR_DURATION_PULLSPRING) is None
    assert state.attributes.get(ATTR_NUMERIC_STATE) == 2
    assert state.attributes.get(ATTR_SEMI_LOCKED) is False
    assert state.attributes.get(ATTR_SUPPORT_PULLSPING) is False
    assert state.attributes.get(ATTR_BATTERY_CHARGING) is None

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "98765-lock"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, 98765)}
    assert device.manufacturer == "tedee"
    assert device.name == "Lock-2C3D"
    assert device.model == "Tedee GO"

    with pytest.raises(
        HomeAssistantError,
        match="Entity lock.lock_2c3d_lock does not support this service.",
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_OPEN,
            {
                ATTR_ENTITY_ID: "lock.lock_2c3d_lock",
            },
            blocking=True,
        )

    assert len(mock_tedee.open.mock_calls) == 0
