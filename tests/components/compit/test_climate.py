"""Tests for the Compit climate platform."""

from unittest.mock import MagicMock

from compit_inext_api.consts import (
    CompitFanMode,
    CompitHVACMode,
    CompitParameter,
    CompitPresetMode,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_compit_entities

from tests.common import MockConfigEntry

CLIMATE_R900 = "climate.r_900"
CLIMATE_NANO_COLOR_2 = "climate.nano_color_2"


def _make_climate_values(
    hvac_mode: str = CompitHVACMode.HEAT.value,
    preset_mode: str = CompitPresetMode.AUTO.value,
    fan_mode: str = CompitFanMode.AUTO.value,
    current_temp: float = 21.0,
    target_temp: float = 22.0,
) -> dict:
    return {
        CompitParameter.HVAC_MODE: hvac_mode,
        CompitParameter.PRESET_MODE: preset_mode,
        CompitParameter.FAN_MODE: fan_mode,
        CompitParameter.CURRENT_TEMPERATURE: current_temp,
        CompitParameter.SET_TARGET_TEMPERATURE: target_temp,
    }


async def test_climate_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test for climate entities creation, unique IDs, and device info."""
    values = _make_climate_values()
    mock_connector.get_current_value.side_effect = lambda device_id, param: values.get(
        param
    )
    await setup_integration(hass, mock_config_entry)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.CLIMATE)


async def test_climate_unknown_device_not_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test that devices with unknown definition codes do not create climate entities."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: None
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CLIMATE_R900) is not None
    assert hass.states.get(CLIMATE_NANO_COLOR_2) is not None
    assert len(hass.states.async_all(Platform.CLIMATE)) == 2


async def test_climate_state_unknown_when_hvac_mode_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test climate entity state is unknown when hvac mode returns None."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: None
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(CLIMATE_NANO_COLOR_2)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("current_temperature") is None
    assert state.attributes.get("temperature") is None
    assert state.attributes.get("preset_mode") is None
    assert state.attributes.get("fan_mode") is None


async def test_climate_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test setting the target temperature."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: None
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: CLIMATE_NANO_COLOR_2, ATTR_TEMPERATURE: 23.5},
        blocking=True,
    )

    mock_connector.set_device_parameter.assert_called_once_with(
        2, CompitParameter.SET_TARGET_TEMPERATURE, 23.5
    )


@pytest.mark.parametrize(
    ("ha_mode", "expected_compit_mode"),
    [
        pytest.param(HVACMode.COOL, CompitHVACMode.COOL, id="cool"),
        pytest.param(HVACMode.HEAT, CompitHVACMode.HEAT, id="heat"),
        pytest.param(HVACMode.OFF, CompitHVACMode.OFF, id="off"),
    ],
)
async def test_climate_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    ha_mode: HVACMode,
    expected_compit_mode: CompitHVACMode,
) -> None:
    """Test setting HVAC mode."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: None
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE_NANO_COLOR_2, ATTR_HVAC_MODE: ha_mode},
        blocking=True,
    )

    mock_connector.set_device_parameter.assert_called_once_with(
        2, CompitParameter.HVAC_MODE, expected_compit_mode.value
    )


@pytest.mark.parametrize(
    ("ha_preset", "expected_compit_preset"),
    [
        pytest.param(PRESET_HOME, CompitPresetMode.AUTO, id="home"),
        pytest.param(PRESET_ECO, CompitPresetMode.HOLIDAY, id="eco"),
        pytest.param(PRESET_NONE, CompitPresetMode.MANUAL, id="none"),
        pytest.param(PRESET_AWAY, CompitPresetMode.AWAY, id="away"),
    ],
)
async def test_climate_set_preset_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    ha_preset: str,
    expected_compit_preset: CompitPresetMode,
) -> None:
    """Test setting preset mode."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: None
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: CLIMATE_NANO_COLOR_2, ATTR_PRESET_MODE: ha_preset},
        blocking=True,
    )

    mock_connector.set_device_parameter.assert_called_once_with(
        2, CompitParameter.PRESET_MODE, expected_compit_preset.value
    )


@pytest.mark.parametrize(
    ("ha_fan_mode", "expected_compit_fan_mode"),
    [
        pytest.param(FAN_OFF, CompitFanMode.OFF, id="off"),
        pytest.param(
            FAN_AUTO, CompitFanMode.HOLIDAY, id="auto"
        ),  # HOLIDAY overwrites AUTO in the reverse map (both map to FAN_AUTO)
        pytest.param(FAN_LOW, CompitFanMode.LOW, id="low"),
        pytest.param(FAN_MEDIUM, CompitFanMode.MEDIUM, id="medium"),
        pytest.param(FAN_HIGH, CompitFanMode.HIGH, id="high"),
    ],
)
async def test_climate_set_fan_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    ha_fan_mode: str,
    expected_compit_fan_mode: CompitFanMode,
) -> None:
    """Test setting fan mode."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: None
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: CLIMATE_NANO_COLOR_2, ATTR_FAN_MODE: ha_fan_mode},
        blocking=True,
    )

    mock_connector.set_device_parameter.assert_called_once_with(
        2, CompitParameter.FAN_MODE, expected_compit_fan_mode.value
    )


@pytest.mark.parametrize(
    ("hvac_value", "expected_ha_mode"),
    [
        pytest.param(CompitHVACMode.COOL.value, HVACMode.COOL, id="cool"),
        pytest.param(CompitHVACMode.HEAT.value, HVACMode.HEAT, id="heat"),
        pytest.param(CompitHVACMode.OFF.value, HVACMode.OFF, id="off"),
    ],
)
async def test_climate_hvac_mode_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    hvac_value: str,
    expected_ha_mode: HVACMode,
) -> None:
    """Test that HVAC mode is correctly translated to HA state."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: (
        hvac_value if param == CompitParameter.HVAC_MODE else None
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(CLIMATE_NANO_COLOR_2)
    assert state is not None
    assert state.state == expected_ha_mode


@pytest.mark.parametrize(
    ("preset_value", "expected_ha_preset"),
    [
        pytest.param(CompitPresetMode.AUTO.value, PRESET_HOME, id="home"),
        pytest.param(CompitPresetMode.HOLIDAY.value, PRESET_ECO, id="eco"),
        pytest.param(CompitPresetMode.MANUAL.value, PRESET_NONE, id="none"),
        pytest.param(CompitPresetMode.AWAY.value, PRESET_AWAY, id="away"),
    ],
)
async def test_climate_preset_mode_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    preset_value: str,
    expected_ha_preset: str,
) -> None:
    """Test that preset mode is correctly translated to HA preset."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: (
        preset_value if param == CompitParameter.PRESET_MODE else None
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(CLIMATE_NANO_COLOR_2)
    assert state is not None
    assert state.attributes.get("preset_mode") == expected_ha_preset


@pytest.mark.parametrize(
    ("fan_value", "expected_ha_fan"),
    [
        pytest.param(CompitFanMode.OFF.value, FAN_OFF, id="off"),
        pytest.param(CompitFanMode.AUTO.value, FAN_AUTO, id="auto"),
        pytest.param(CompitFanMode.LOW.value, FAN_LOW, id="low"),
        pytest.param(CompitFanMode.MEDIUM.value, FAN_MEDIUM, id="medium"),
        pytest.param(CompitFanMode.HIGH.value, FAN_HIGH, id="high"),
    ],
)
async def test_climate_fan_mode_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    fan_value: str,
    expected_ha_fan: str,
) -> None:
    """Test that fan mode is correctly translated to HA fan mode."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: (
        fan_value if param == CompitParameter.FAN_MODE else None
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(CLIMATE_NANO_COLOR_2)
    assert state is not None
    assert state.attributes.get("fan_mode") == expected_ha_fan


async def test_climate_r900_preset_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test R 900 device sets preset mode."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: None
    mock_connector.set_device_parameter.side_effect = None
    mock_connector.set_device_parameter.return_value = True
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: CLIMATE_R900, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    mock_connector.set_device_parameter.assert_called_once_with(
        1, CompitParameter.PRESET_MODE, CompitPresetMode.AWAY.value
    )


async def test_climate_r900_supported_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test R 900 only supports preset mode (no fan or target temperature)."""
    mock_connector.get_current_value.side_effect = lambda device_id, param: None
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(CLIMATE_R900)
    assert state is not None
    assert state.attributes.get("fan_mode") is None
    assert state.attributes.get("temperature") is None
    assert state.attributes.get("preset_modes") == [PRESET_HOME, PRESET_AWAY]
    assert state.attributes.get("hvac_modes") == [HVACMode.HEAT, HVACMode.OFF]
