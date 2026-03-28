"""Tests for the TOLO Sauna sensor platform."""

from unittest.mock import MagicMock

import pytest
from tololib import (
    AromaTherapySlot,
    Calefaction,
    LampMode,
    Model,
    ToloSettings,
    ToloStatus,
)

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Entity IDs based on registration order:
# water_level, tank_temperature, power_timer_remaining, salt_bath_timer_remaining, fan_timer_remaining
WATER_LEVEL_ENTITY_ID = "sensor.tolo_sauna"
TANK_TEMPERATURE_ENTITY_ID = "sensor.tolo_sauna_2"
POWER_TIMER_REMAINING_ENTITY_ID = "sensor.tolo_sauna_3"
SALT_BATH_TIMER_REMAINING_ENTITY_ID = "sensor.tolo_sauna_4"
FAN_TIMER_REMAINING_ENTITY_ID = "sensor.tolo_sauna_5"


@pytest.mark.usefixtures("init_integration")
async def test_water_level_sensor(
    hass: HomeAssistant,
) -> None:
    """Test water level sensor value."""
    state = hass.states.get(WATER_LEVEL_ENTITY_ID)
    assert state is not None
    # water_level=2 -> water_level_percent=66
    assert state.state == "66"


@pytest.mark.usefixtures("init_integration")
async def test_tank_temperature_sensor(
    hass: HomeAssistant,
) -> None:
    """Test tank temperature sensor value."""
    state = hass.states.get(TANK_TEMPERATURE_ENTITY_ID)
    assert state is not None
    assert state.state == "50"


@pytest.mark.usefixtures("init_integration")
async def test_power_timer_remaining_sensor(
    hass: HomeAssistant,
) -> None:
    """Test power timer remaining sensor when power on and timer set."""
    state = hass.states.get(POWER_TIMER_REMAINING_ENTITY_ID)
    assert state is not None
    assert state.state == "10"


@pytest.mark.usefixtures("init_integration")
async def test_salt_bath_timer_remaining_sensor(
    hass: HomeAssistant,
) -> None:
    """Test salt bath timer remaining sensor when salt bath on and timer set."""
    state = hass.states.get(SALT_BATH_TIMER_REMAINING_ENTITY_ID)
    assert state is not None
    assert state.state == "15"


@pytest.mark.usefixtures("init_integration")
async def test_fan_timer_remaining_sensor(
    hass: HomeAssistant,
) -> None:
    """Test fan timer remaining sensor when fan on and timer set."""
    state = hass.states.get(FAN_TIMER_REMAINING_ENTITY_ID)
    assert state is not None
    assert state.state == "5"


async def test_power_timer_remaining_unavailable_when_power_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test power timer remaining is unavailable when power is off."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=False,
        current_temperature=30,
        power_timer=None,
        flow_in=False,
        flow_out=False,
        calefaction=Calefaction.INACTIVE,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=False,
        water_level=0,
        fan_on=False,
        fan_timer=None,
        current_humidity=50,
        tank_temperature=30,
        model=Model.DOMESTIC,
        salt_bath_on=False,
        salt_bath_timer=None,
    )
    mock_tolo_client.get_settings.return_value = ToloSettings(
        target_temperature=50,
        power_timer=30,
        aroma_therapy_slot=AromaTherapySlot.A,
        sweep_timer=None,
        fan_timer=20,
        target_humidity=80,
        salt_bath_timer=25,
        lamp_mode=LampMode.MANUAL,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(POWER_TIMER_REMAINING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_power_timer_remaining_unavailable_when_timer_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test power timer remaining is unavailable when settings timer is None."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=True,
        current_temperature=45,
        power_timer=10,
        flow_in=True,
        flow_out=False,
        calefaction=Calefaction.HEAT,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=True,
        water_level=2,
        fan_on=True,
        fan_timer=5,
        current_humidity=70,
        tank_temperature=50,
        model=Model.DOMESTIC,
        salt_bath_on=True,
        salt_bath_timer=15,
    )
    mock_tolo_client.get_settings.return_value = ToloSettings(
        target_temperature=50,
        power_timer=None,
        aroma_therapy_slot=AromaTherapySlot.A,
        sweep_timer=None,
        fan_timer=20,
        target_humidity=80,
        salt_bath_timer=25,
        lamp_mode=LampMode.MANUAL,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(POWER_TIMER_REMAINING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_salt_bath_timer_remaining_unavailable_when_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test salt bath timer remaining is unavailable when salt bath is off."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=True,
        current_temperature=45,
        power_timer=10,
        flow_in=True,
        flow_out=False,
        calefaction=Calefaction.HEAT,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=True,
        water_level=2,
        fan_on=True,
        fan_timer=5,
        current_humidity=70,
        tank_temperature=50,
        model=Model.DOMESTIC,
        salt_bath_on=False,
        salt_bath_timer=None,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(SALT_BATH_TIMER_REMAINING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_fan_timer_remaining_unavailable_when_fan_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test fan timer remaining is unavailable when fan is off."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=True,
        current_temperature=45,
        power_timer=10,
        flow_in=True,
        flow_out=False,
        calefaction=Calefaction.HEAT,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=True,
        water_level=2,
        fan_on=False,
        fan_timer=None,
        current_humidity=70,
        tank_temperature=50,
        model=Model.DOMESTIC,
        salt_bath_on=True,
        salt_bath_timer=15,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(FAN_TIMER_REMAINING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_water_level_always_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test water level sensor is always available (no availability_checker)."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=False,
        current_temperature=30,
        power_timer=None,
        flow_in=False,
        flow_out=False,
        calefaction=Calefaction.INACTIVE,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=False,
        water_level=0,
        fan_on=False,
        fan_timer=None,
        current_humidity=50,
        tank_temperature=30,
        model=Model.DOMESTIC,
        salt_bath_on=False,
        salt_bath_timer=None,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(WATER_LEVEL_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "0"
