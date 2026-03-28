"""Tests for the TOLO Sauna climate platform."""

from unittest.mock import MagicMock

import pytest
from tololib import Calefaction, Model, ToloStatus

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_OFF,
    FAN_ON,
    HVACAction,
    HVACMode,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CLIMATE_ENTITY_ID = "climate.tolo_sauna"


@pytest.mark.usefixtures("init_integration")
async def test_climate_state(
    hass: HomeAssistant,
) -> None:
    """Test climate entity state and attributes."""
    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 45
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 70
    assert state.attributes[ATTR_TEMPERATURE] == 50
    assert state.attributes[ATTR_HUMIDITY] == 80
    assert state.attributes[ATTR_FAN_MODE] == FAN_ON
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes[ATTR_MIN_TEMP] == 35
    assert state.attributes[ATTR_MAX_TEMP] == 60
    assert state.attributes[ATTR_MIN_HUMIDITY] == 60
    assert state.attributes[ATTR_MAX_HUMIDITY] == 99
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test setting the target temperature."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 55},
        blocking=True,
    )
    mock_tolo_client.set_target_temperature.assert_called_once_with(55)


@pytest.mark.usefixtures("init_integration")
async def test_set_humidity(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test setting the target humidity."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_HUMIDITY: 90},
        blocking=True,
    )
    mock_tolo_client.set_target_humidity.assert_called_once_with(90)


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_mode(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test setting the fan mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_FAN_MODE: FAN_OFF},
        blocking=True,
    )
    mock_tolo_client.set_fan_on.assert_called_once_with(False)

    mock_tolo_client.set_fan_on.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_FAN_MODE: FAN_ON},
        blocking=True,
    )
    mock_tolo_client.set_fan_on.assert_called_once_with(True)


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test setting HVAC mode to off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_tolo_client.set_power_on.assert_called_once_with(False)
    mock_tolo_client.set_fan_on.assert_called_once_with(False)


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test setting HVAC mode to heat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_tolo_client.set_power_on.assert_called_once_with(True)
    mock_tolo_client.set_fan_on.assert_called_once_with(False)


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_dry(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test setting HVAC mode to dry."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.DRY},
        blocking=True,
    )
    mock_tolo_client.set_power_on.assert_called_once_with(False)
    mock_tolo_client.set_fan_on.assert_called_once_with(True)


@pytest.mark.usefixtures("init_integration")
async def test_turn_on(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning on the climate entity."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_power_on.assert_called_once_with(True)
    mock_tolo_client.set_fan_on.assert_called_once_with(False)


@pytest.mark.usefixtures("init_integration")
async def test_turn_off(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test turning off the climate entity."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID},
        blocking=True,
    )
    mock_tolo_client.set_power_on.assert_called_once_with(False)
    mock_tolo_client.set_fan_on.assert_called_once_with(False)


async def test_hvac_mode_off_when_power_off_fan_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test HVAC mode is off when power and fan are off."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=False,
        current_temperature=45,
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

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF


async def test_hvac_mode_dry_when_power_off_fan_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test HVAC mode is dry when power off but fan is on."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=False,
        current_temperature=45,
        power_timer=None,
        flow_in=False,
        flow_out=False,
        calefaction=Calefaction.INACTIVE,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=False,
        water_level=0,
        fan_on=True,
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

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.DRY
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.DRYING


async def test_hvac_action_idle_when_calefaction_keep(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test HVAC action is idle when calefaction is KEEP."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=True,
        current_temperature=50,
        power_timer=10,
        flow_in=True,
        flow_out=False,
        calefaction=Calefaction.KEEP,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=True,
        water_level=2,
        fan_on=False,
        fan_timer=None,
        current_humidity=80,
        tank_temperature=50,
        model=Model.DOMESTIC,
        salt_bath_on=False,
        salt_bath_timer=None,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_hvac_action_none_when_calefaction_unclear(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> None:
    """Test HVAC action is None when calefaction is UNCLEAR."""
    mock_tolo_client.get_status.return_value = ToloStatus(
        power_on=True,
        current_temperature=50,
        power_timer=10,
        flow_in=True,
        flow_out=False,
        calefaction=Calefaction.UNCLEAR,
        aroma_therapy_on=False,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=True,
        water_level=2,
        fan_on=False,
        fan_timer=None,
        current_humidity=80,
        tank_temperature=50,
        model=Model.DOMESTIC,
        salt_bath_on=False,
        salt_bath_timer=None,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state is not None
    assert ATTR_HVAC_ACTION not in state.attributes
