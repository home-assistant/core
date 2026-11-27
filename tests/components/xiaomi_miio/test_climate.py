"""The tests for the xiaomi_miio climate component."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from miio import DeviceException, HeaterMiot
from miio.heater_miot import HeaterMiotStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.components.xiaomi_miio.const import CONF_FLOW_TYPE, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import TEST_MAC

ENTITY_ID = "climate.test_heater"

_STATUS = {
    "zhimi.heater.mc2": {
        "power": True,
        "target_temperature": 22,
        "countdown_time": 0,
        "temperature": 19.5,
        "child_lock": False,
        "buzzer": True,
        "led_brightness": 0,
    },
    "zhimi.heater.za2": {
        "power": False,
        "target_temperature": 20,
        "countdown_time": 0,
        "temperature": 21.0,
        "relative_humidity": 45,
        "child_lock": False,
        "buzzer": True,
        "led_brightness": 0,
    },
}


@pytest.fixture(name="model_code", params=_STATUS.keys())
def get_model_code(request: pytest.FixtureRequest) -> str:
    """Parametrize model code."""
    return request.param


@pytest.fixture(name="mock_heater")
def setup_device(model_code: str) -> Generator[MagicMock]:
    """Mock the heater device."""
    mock_heater = MagicMock(spec=HeaterMiot)
    mock_heater.status.return_value = HeaterMiotStatus(_STATUS[model_code], model_code)
    with patch(
        "homeassistant.components.xiaomi_miio.HeaterMiot",
        return_value=mock_heater,
    ):
        yield mock_heater


async def setup_component(
    hass: HomeAssistant, model_code: str, unique_id: str | None = "123456"
) -> MockConfigEntry:
    """Set up the climate component."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        title="Test heater",
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: model_code,
            CONF_MAC: TEST_MAC,
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def test_climate_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_heater: MagicMock,
    model_code: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the heater state."""
    config_entry = await setup_component(hass, model_code)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_set_temperature(
    hass: HomeAssistant, mock_heater: MagicMock, model_code: str
) -> None:
    """Test setting the target temperature."""
    await setup_component(hass, model_code)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 24},
        blocking=True,
    )
    mock_heater.set_target_temperature.assert_called_once_with(24)


async def test_set_temperature_fahrenheit(
    hass: HomeAssistant, mock_heater: MagicMock, model_code: str
) -> None:
    """Test a Fahrenheit target temperature is rounded to the nearest degree."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await setup_component(hass, model_code)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 75},
        blocking=True,
    )
    # 75 °F is 23.9 °C
    mock_heater.set_target_temperature.assert_called_once_with(24)


@pytest.mark.parametrize(
    ("hvac_mode", "method"),
    [(HVACMode.HEAT, "on"), (HVACMode.OFF, "off")],
)
async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
    mock_heater: MagicMock,
    model_code: str,
    hvac_mode: HVACMode,
    method: str,
) -> None:
    """Test setting the target temperature together with the HVAC mode."""
    await setup_component(hass, model_code)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 24, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )
    getattr(mock_heater, method).assert_called_once_with()
    mock_heater.set_target_temperature.assert_called_once_with(24)


async def test_setup_without_unique_id(
    hass: HomeAssistant, mock_heater: MagicMock, model_code: str
) -> None:
    """Test the heater is set up when the config entry has no unique ID."""
    await setup_component(hass, model_code, unique_id=None)
    assert len(hass.states.async_entity_ids(CLIMATE_DOMAIN)) == 1


@pytest.mark.parametrize(
    ("service", "data", "method"),
    [
        (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.HEAT}, "on"),
        (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.OFF}, "off"),
        (SERVICE_TURN_ON, {}, "on"),
        (SERVICE_TURN_OFF, {}, "off"),
    ],
)
async def test_power(
    hass: HomeAssistant,
    mock_heater: MagicMock,
    model_code: str,
    service: str,
    data: dict,
    method: str,
) -> None:
    """Test turning the heater on and off."""
    await setup_component(hass, model_code)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )
    getattr(mock_heater, method).assert_called_once_with()


async def test_command_error(
    hass: HomeAssistant, mock_heater: MagicMock, model_code: str
) -> None:
    """Test an error sending a command to the heater."""
    await setup_component(hass, model_code)
    mock_heater.set_target_temperature.side_effect = DeviceException("timeout")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 24},
            blocking=True,
        )
    assert exc_info.value.translation_key == "heater_command_failed"
