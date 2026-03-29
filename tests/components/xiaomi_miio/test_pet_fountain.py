"""Tests for the Xiaomi pet fountain support."""

from datetime import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE as NUMBER_SET_VALUE,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE as TIME_SET_VALUE,
)
from homeassistant.components.xiaomi_miio.const import (
    CONF_FLOW_TYPE,
    DOMAIN,
    MODEL_PET_FOUNTAIN_70M2,
)
from homeassistant.components.xiaomi_miio.pet_fountain_miot import (
    ChargingState,
    PetFountainMode,
    PetFountainStatus,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TEST_MAC

from tests.common import MockConfigEntry


@pytest.fixture
def mock_pet_fountain():
    """Mock the Xiaomi Pet Fountain device."""
    mock_device = MagicMock()
    mock_device.status.return_value = SimpleNamespace(
        is_on=True,
        status=PetFountainStatus.NoWater,
        water_shortage=False,
        pump_blocked=False,
        has_fault=True,
        mode=PetFountainMode.Auto,
        water_interval=25,
        do_not_disturb=False,
        child_lock=False,
        battery=76,
        low_battery=False,
        charging_state=ChargingState.NotCharging,
        usb_power=False,
        filter_life_remaining=89,
        filter_left_time=12.5,
        fault_code=1,
        dnd_start=time(22, 0),
        dnd_end=time(8, 30),
    )
    mock_device.set_mode.return_value = [{"code": 0}]
    mock_device.set_water_interval.return_value = [{"code": 0}]
    mock_device.set_do_not_disturb.return_value = [{"code": 0}]
    mock_device.set_child_lock.return_value = [{"code": 0}]
    mock_device.set_dnd_start.return_value = [{"code": 0}]
    mock_device.set_dnd_end.return_value = [{"code": 0}]
    mock_device.reset_filter_life.return_value = {"code": 0}

    with patch(
        "homeassistant.components.xiaomi_miio.XiaomiPetFountain",
        return_value=mock_device,
    ):
        yield mock_device


async def test_pet_fountain_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pet_fountain,
) -> None:
    """Test the pet fountain entity set."""
    base_entity_id = await setup_component(hass, "test_pet_fountain")
    water_shortage_entity_id = "binary_sensor.test_pet_fountain_water_shortage"
    pump_blocked_entity_id = "binary_sensor.test_pet_fountain_pump_blocked"
    usb_power_entity_id = "binary_sensor.test_pet_fountain_usb_power"
    water_mode_entity_id = f"{SELECT_DOMAIN}.test_pet_fountain_water_mode"
    water_interval_entity_id = f"{NUMBER_DOMAIN}.test_pet_fountain_water_interval"
    dnd_start_entity_id = f"{TIME_DOMAIN}.test_pet_fountain_do_not_disturb_start"
    dnd_end_entity_id = f"{TIME_DOMAIN}.test_pet_fountain_do_not_disturb_end"
    reset_filter_entity_id = f"{BUTTON_DOMAIN}.test_pet_fountain_reset_filter"

    assert hass.states.get(f"{base_entity_id}_status").state == "no_water"
    assert float(hass.states.get(f"{base_entity_id}_filter_life_remaining").state) == 89
    assert (
        float(hass.states.get(f"{base_entity_id}_filter_time_remaining").state) == 12.5
    )
    assert float(hass.states.get(f"{base_entity_id}_battery_level").state) == 76
    assert hass.states.get(f"{base_entity_id}_charging_state").state == "not_charging"
    assert hass.states.get(water_shortage_entity_id).state == "off"
    assert hass.states.get(pump_blocked_entity_id).state == "off"
    assert hass.states.get(usb_power_entity_id).state == "off"
    assert hass.states.get(water_mode_entity_id).state == "auto"
    assert float(hass.states.get(water_interval_entity_id).state) == 25
    assert hass.states.get("switch.test_pet_fountain_do_not_disturb").state == "off"
    assert hass.states.get("switch.test_pet_fountain_child_lock").state == "off"
    assert hass.states.get(dnd_start_entity_id).state == "22:00:00"
    assert hass.states.get(dnd_end_entity_id).state == "08:30:00"
    assert hass.states.get(reset_filter_entity_id).state == "unknown"

    assert hass.states.get("binary_sensor.test_pet_fountain_fault") is None
    assert hass.states.get("sensor.test_pet_fountain_fault_code") is None

    fault_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "has_fault_123456"
    )
    assert fault_entity_id == "binary_sensor.test_pet_fountain_fault"
    fault_entity = entity_registry.async_get(fault_entity_id)
    assert fault_entity is not None
    assert fault_entity.disabled_by is not None

    fault_code_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "fault_code_123456"
    )
    assert fault_code_entity_id == "sensor.test_pet_fountain_fault_code"
    fault_code_entity = entity_registry.async_get(fault_code_entity_id)
    assert fault_code_entity is not None
    assert fault_code_entity.disabled_by is not None


async def test_pet_fountain_controls(
    hass: HomeAssistant,
    mock_pet_fountain,
) -> None:
    """Test the pet fountain controls."""
    await setup_component(hass, "test_pet_fountain")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.test_pet_fountain_water_mode",
            ATTR_OPTION: "interval",
        },
        blocking=True,
    )
    mock_pet_fountain.set_mode.assert_called_once_with(PetFountainMode.Interval)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_pet_fountain_water_interval",
            ATTR_VALUE: 30,
        },
        blocking=True,
    )
    mock_pet_fountain.set_water_interval.assert_called_once_with(30)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: "switch.test_pet_fountain_do_not_disturb"},
        blocking=True,
    )
    mock_pet_fountain.set_do_not_disturb.assert_called_once_with(True)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: "switch.test_pet_fountain_child_lock"},
        blocking=True,
    )
    mock_pet_fountain.set_child_lock.assert_called_once_with(True)

    await hass.services.async_call(
        TIME_DOMAIN,
        TIME_SET_VALUE,
        {
            ATTR_ENTITY_ID: "time.test_pet_fountain_do_not_disturb_start",
            ATTR_TIME: "23:15:00",
        },
        blocking=True,
    )
    mock_pet_fountain.set_dnd_start.assert_called_once_with(time(23, 15))

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_pet_fountain_reset_filter"},
        blocking=True,
    )
    mock_pet_fountain.reset_filter_life.assert_called_once_with()


async def setup_component(hass: HomeAssistant, entry_title: str) -> str:
    """Set up the pet fountain component."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        title=entry_title,
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "0.0.0.0",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: MODEL_PET_FOUNTAIN_70M2,
            CONF_MAC: TEST_MAC,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return f"sensor.{entry_title}"
