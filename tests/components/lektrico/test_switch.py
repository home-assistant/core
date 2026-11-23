"""Tests for the Lektrico switch platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

from pytest_homeassistant.common import (
    MockConfigEntry,
    load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lektrico.const import (
    CONF_HW_VERSION,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_TYPE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCKED_DEVICE_IP_ADDRESS, MOCKED_DEVICE_SERIAL_NUMBER

COMPATIBILITY_MODE_ENTITY_ID = "switch.1p7k_500006_compatibility_mode"


def _device_info(**overrides: Any) -> dict[str, Any]:
    """Return the device info fixture with the given overrides applied."""
    data = load_json_object_fixture("get_info.json", DOMAIN)
    data.update(overrides)
    return data


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""

    with patch.multiple(
        "homeassistant.components.lektrico",
        CHARGERS_PLATFORMS=[Platform.SWITCH],
        LB_DEVICES_PLATFORMS=[Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on_compatibility_mode(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the compatibility mode switch on."""
    mock_device.device_info.return_value = _device_info(precise_pwm_mode=False)

    with patch.multiple(
        "homeassistant.components.lektrico",
        CHARGERS_PLATFORMS=[Platform.SWITCH],
        LB_DEVICES_PLATFORMS=[Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(COMPATIBILITY_MODE_ENTITY_ID).state == STATE_OFF

    mock_device.device_info.return_value = _device_info(precise_pwm_mode=True)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: COMPATIBILITY_MODE_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_device.set_compatibility_mode.assert_awaited_once_with(True)
    assert hass.states.get(COMPATIBILITY_MODE_ENTITY_ID).state == STATE_ON


async def test_turn_off_compatibility_mode(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the compatibility mode switch off."""
    with patch.multiple(
        "homeassistant.components.lektrico",
        CHARGERS_PLATFORMS=[Platform.SWITCH],
        LB_DEVICES_PLATFORMS=[Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(COMPATIBILITY_MODE_ENTITY_ID).state == STATE_ON

    mock_device.device_info.return_value = _device_info(precise_pwm_mode=False)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: COMPATIBILITY_MODE_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_device.set_compatibility_mode.assert_awaited_once_with(False)
    assert hass.states.get(COMPATIBILITY_MODE_ENTITY_ID).state == STATE_OFF


async def test_compatibility_mode_not_created_for_three_phase_charger(
    hass: HomeAssistant,
    mock_device: AsyncMock,
) -> None:
    """Test the compatibility mode switch is created for 1P7K chargers only."""
    mock_device.device_config.return_value = {
        "type": "3p22k",
        "serial_number": MOCKED_DEVICE_SERIAL_NUMBER,
        "board_revision": "B",
    }
    mock_device.device_info.return_value = _device_info(
        precise_pwm_mode=True, relay_mode=3
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
            CONF_TYPE: "3p22k",
            CONF_SERIAL_NUMBER: MOCKED_DEVICE_SERIAL_NUMBER,
            CONF_HW_VERSION: "B",
        },
        unique_id=MOCKED_DEVICE_SERIAL_NUMBER,
    )

    with patch.multiple(
        "homeassistant.components.lektrico",
        CHARGERS_PLATFORMS=[Platform.SWITCH],
        LB_DEVICES_PLATFORMS=[Platform.SWITCH],
    ):
        await setup_integration(hass, config_entry)

    assert hass.states.get("switch.3p22k_500006_compatibility_mode") is None
    assert hass.states.get("switch.3p22k_500006_force_single_phase") is not None
