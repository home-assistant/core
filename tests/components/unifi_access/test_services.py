"""Tests for UniFi Access services."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from unifi_access_api import (
    DoorLockRule,
    DoorLockRuleStatus,
    DoorLockRuleType,
    UnifiAccessError,
)

from homeassistant.components.unifi_access.const import (
    ATTR_INTERVAL,
    ATTR_RULE,
    DOMAIN,
    SERVICE_SET_LOCK_RULE,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry

FRONT_DOOR_LOCK_RULE_ENTITY = "sensor.front_door_lock_rule"


def _device_id(device_registry: dr.DeviceRegistry, identifier: str) -> str:
    """Return the device ID for a UniFi Access identifier."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, identifier)})
    assert device is not None
    return device.id


async def test_set_lock_rule_service_calls_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the lock-rule service calls the API with the provided interval."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_RULE,
        {
            ATTR_DEVICE_ID: _device_id(device_registry, "door-001"),
            ATTR_RULE: "keep_lock",
            ATTR_INTERVAL: {"minutes": 30},
        },
        blocking=True,
    )

    mock_client.set_door_lock_rule.assert_awaited_once_with(
        "door-001", DoorLockRule(type=DoorLockRuleType.KEEP_LOCK, interval=30)
    )


async def test_set_lock_rule_service_defaults_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the lock-rule service uses the default interval when omitted."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_RULE,
        {
            ATTR_DEVICE_ID: _device_id(device_registry, "door-001"),
            ATTR_RULE: "keep_unlock",
        },
        blocking=True,
    )

    mock_client.set_door_lock_rule.assert_awaited_once_with(
        "door-001", DoorLockRule(type=DoorLockRuleType.KEEP_UNLOCK, interval=10)
    )


async def test_set_lock_rule_service_updates_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the lock-rule service updates the cached sensor state."""
    mock_client.get_door_lock_rule = AsyncMock(return_value=DoorLockRuleStatus())
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_RULE,
        {
            ATTR_DEVICE_ID: _device_id(device_registry, "door-001"),
            ATTR_RULE: "keep_lock",
        },
        blocking=True,
    )

    state = hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY)
    assert state is not None
    assert state.state == "keep_lock"


async def test_set_lock_rule_service_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the lock-rule service raises a translated error on API failure."""
    await setup_integration(hass, mock_config_entry)
    mock_client.set_door_lock_rule = AsyncMock(
        side_effect=UnifiAccessError("API error")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_RULE,
            {
                ATTR_DEVICE_ID: _device_id(device_registry, "door-001"),
                ATTR_RULE: "keep_lock",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "lock_rule_failed"
    assert exc_info.value.translation_domain == DOMAIN


async def test_set_lock_rule_service_rejects_hub_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the lock-rule service rejects the hub device as a target."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_RULE,
            {
                ATTR_DEVICE_ID: _device_id(device_registry, mock_config_entry.entry_id),
                ATTR_RULE: "keep_lock",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_target"
    assert exc_info.value.translation_domain == DOMAIN
