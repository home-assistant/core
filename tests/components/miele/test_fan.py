"""Tests for miele fan module."""

from typing import Any
from unittest.mock import MagicMock

from aiohttp import ClientResponseError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

TEST_PLATFORM = FAN_DOMAIN
pytestmark = pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)])

ENTITY_ID = "fan.hood_fan"


@pytest.mark.parametrize("load_device_file", ["fan_devices.json"])
async def test_fan_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test fan entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("load_device_file", ["fan_devices.json"])
@pytest.mark.parametrize(
    ("service", "expected_argument"),
    [
        (SERVICE_TURN_ON, {"powerOn": True}),
        (SERVICE_TURN_OFF, {"powerOff": True}),
    ],
)
async def test_fan_control(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    service: str,
    expected_argument: dict[str, Any],
) -> None:
    """Test the fan can be turned on/off."""

    await hass.services.async_call(
        TEST_PLATFORM,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_miele_client.send_action.assert_called_once_with(
        "DummyAppliance_18", expected_argument
    )


@pytest.mark.parametrize(
    ("service", "percentage", "expected_argument"),
    [
        ("set_percentage", 0, {"powerOff": True}),
        ("set_percentage", 20, {"ventilationStep": 1}),
        ("set_percentage", 100, {"ventilationStep": 4}),
    ],
)
async def test_fan_set_speed(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    service: str,
    percentage: int,
    expected_argument: dict[str, Any],
) -> None:
    """Test the fan can set percentage."""

    await hass.services.async_call(
        TEST_PLATFORM,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )
    mock_miele_client.send_action.assert_called_once_with(
        "DummyAppliance_18", expected_argument
    )


async def test_fan_turn_on_w_percentage(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test the fan can turn on with percentage."""

    await hass.services.async_call(
        TEST_PLATFORM,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    mock_miele_client.send_action.assert_called_with(
        "DummyAppliance_18", {"ventilationStep": 2}
    )


@pytest.mark.parametrize(
    ("service"),
    [
        (SERVICE_TURN_ON),
        (SERVICE_TURN_OFF),
    ],
)
async def test_api_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    service: str,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.send_action.side_effect = ClientResponseError("test", "Test")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TEST_PLATFORM, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    mock_miele_client.send_action.assert_called_once()


async def test_set_percentage(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test handling of exception at set_percentage."""
    mock_miele_client.send_action.side_effect = ClientResponseError("test", "Test")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TEST_PLATFORM,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 50},
            blocking=True,
        )
    mock_miele_client.send_action.assert_called_once()
