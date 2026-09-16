"""Test the Eurotronic Comet WiFi climate entity."""

from datetime import timedelta

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.update_coordinator import REQUEST_REFRESH_DEFAULT_COOLDOWN
from homeassistant.util import dt as dt_util

from . import (
    COMMAND_TOPIC_SETPOINT,
    ENTITY_ID,
    PAYLOAD_OFF,
    PAYLOAD_SETPOINT_16,
    PAYLOAD_SETPOINT_21,
    PAYLOAD_SETPOINT_23,
    PAYLOAD_SETPOINT_25,
)
from .conftest import FakeDevice

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import MqttMockHAClient


@pytest.fixture
def initial_setpoint() -> str:
    """Return the setpoint payload the thermostat reports at setup."""
    return PAYLOAD_SETPOINT_21


@pytest.fixture(autouse=True)
async def setup_entry(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device: FakeDevice,
    mock_config_entry: MockConfigEntry,
    initial_setpoint: str,
) -> None:
    """Set up integration with fake thermostat answering."""
    device.setpoint = initial_setpoint
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("device")
async def test_state(hass: HomeAssistant) -> None:
    """Test the state reflects thermostat replies."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 21.0
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.0


@pytest.mark.usefixtures("device")
async def test_state_off(hass: HomeAssistant) -> None:
    """Test the off reply is shown as off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.usefixtures("device")
async def test_set_temperature(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test setting target temperature writes setpoint."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )
    await hass.async_block_till_done()

    mqtt_mock.async_publish.assert_any_call(
        COMMAND_TOPIC_SETPOINT,
        PAYLOAD_SETPOINT_23,
        0,
        False,
        message_expiry_interval=None,
    )


@pytest.mark.usefixtures("device")
async def test_set_temperature_and_turn_off(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test turning off in the same call overrides temperature."""
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 23.0,
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    published = [call.args[:2] for call in mqtt_mock.async_publish.mock_calls]
    assert (COMMAND_TOPIC_SETPOINT, PAYLOAD_OFF) in published
    assert (COMMAND_TOPIC_SETPOINT, PAYLOAD_SETPOINT_23) not in published


@pytest.mark.usefixtures("device")
async def test_set_temperature_unsupported_hvac_mode(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test an unsupported HVAC mode is rejected."""
    mqtt_mock.async_publish.reset_mock()
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 23.0,
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "not_valid_hvac_mode"
    assert not mqtt_mock.async_publish.mock_calls


@pytest.mark.usefixtures("device")
async def test_turn_off_and_on(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test turning on restores the setpoint from before turning off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()
    mqtt_mock.async_publish.assert_any_call(
        COMMAND_TOPIC_SETPOINT, PAYLOAD_OFF, 0, False, message_expiry_interval=None
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF

    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    mqtt_mock.async_publish.assert_any_call(
        COMMAND_TOPIC_SETPOINT,
        PAYLOAD_SETPOINT_21,
        0,
        False,
        message_expiry_interval=None,
    )
    # The second refresh request is within the coordinator's cooldown.
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN + 1)
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT


@pytest.mark.parametrize("initial_setpoint", [PAYLOAD_OFF])
@pytest.mark.usefixtures("device")
async def test_turn_on_initially_off(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test turning on a thermostat that was off at setup uses the default setpoint."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF

    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    mqtt_mock.async_publish.assert_any_call(
        COMMAND_TOPIC_SETPOINT,
        PAYLOAD_SETPOINT_16,
        0,
        False,
        message_expiry_interval=None,
    )


@pytest.mark.usefixtures("device")
async def test_turn_on_restores_debounced_setpoint(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test turning on restores a setpoint that was set while refreshes were debounced."""
    # The first refresh request runs at once and starts the debounce.
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )
    # Inside the cooldown no refresh runs, so the coordinator does not see 25.
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 25.0},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    mqtt_mock.async_publish.assert_any_call(
        COMMAND_TOPIC_SETPOINT,
        PAYLOAD_SETPOINT_25,
        0,
        False,
        message_expiry_interval=None,
    )
