"""Test the zhong_hong climate platform."""

import pytest
from zhong_hong_hvac.protocol import StatusFanMode, StatusOperation, StatusSwitch

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_LOW,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.components.zhong_hong.const import ALL_FAN_MODES, FAN_MEDIUM_HIGH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_OFF,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DEVICE_ADDRESS, ENTITY_ID, FakeGateway, build_status

from tests.common import MockConfigEntry


async def test_entity_registration(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entity keeps the identifier the YAML platform gave it."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    # The address on the bus is not unique on its own: another gateway can
    # have an air conditioner at the same one.
    assert entity_entry.unique_id == f"{mock_config_entry.entry_id}_1_1"


async def test_push_updates_the_entity(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test a status pushed by the gateway reaches the entity."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    mock_gateway.push_status(build_status())
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 26
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 25
    assert state.attributes[ATTR_FAN_MODE] == FAN_LOW


async def test_push_of_a_switched_off_device(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test a device reporting an operation while off still reads as off."""
    await setup_integration(hass, mock_config_entry)

    mock_gateway.push_status(
        build_status(switch=StatusSwitch.OFF, operation=StatusOperation.HEAT)
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_push_of_an_unknown_operation(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test a device that is on but reports an operation we cannot decode."""
    await setup_integration(hass, mock_config_entry)

    # 0x7F is not one of the operations the library knows about, so it decodes
    # to None while the device still reports itself as switched on.
    mock_gateway.push_status(build_status(operation=0x7F))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


async def test_turn_on_success(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn_on does not raise when the command is sent."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )


@pytest.mark.parametrize(
    ("service", "service_data", "command"),
    [
        (SERVICE_TURN_ON, {}, "turn-on"),
        (SERVICE_TURN_OFF, {}, "turn-off"),
        (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 25}, "temperature"),
        (SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: FAN_LOW}, "fan"),
    ],
)
async def test_command_send_failure_raises(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, object],
    command: str,
) -> None:
    """Test a command that cannot be sent surfaces as an error."""
    mock_gateway.send_result = False
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID} | service_data,
            blocking=True,
        )

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_placeholders == {"command": command}


async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting the temperature and the mode in one call sends both."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 25,
            ATTR_HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )

    # Temperature, then the implicit turn-on the device needs, then the mode.
    assert mock_gateway.send_calls == 3


async def test_set_hvac_mode_send_failure_raises(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test set_hvac_mode raises when the mode command cannot be sent."""
    # The device is off, so set_hvac_mode turns it on first. Let that command
    # succeed and fail only the mode command that follows it.
    mock_gateway.send_results = [True, False]
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_placeholders == {"command": "mode"}


async def test_set_hvac_mode_success(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test set_hvac_mode does not raise when the command is sent."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )


async def test_set_hvac_mode_off_turns_the_device_off(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test switching to off only sends the power command."""
    await setup_integration(hass, mock_config_entry)

    mock_gateway.push_status(build_status())
    await hass.async_block_till_done()
    sent_before = mock_gateway.send_calls

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    assert mock_gateway.send_calls == sent_before + 1


async def test_set_fan_mode_success(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test set_fan_mode does not raise when the command is sent."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: FAN_LOW},
        blocking=True,
    )

    assert mock_gateway.send_calls == 1


async def test_set_fan_mode_unsupported_logs_error(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unsupported fan mode logs an error and sends nothing."""
    await setup_integration(hass, mock_config_entry)

    # The service call is not usable here: climate rejects a fan mode outside
    # fan_modes before it ever reaches the entity, so the guard under test can
    # only be exercised by calling the entity method directly.
    entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)
    assert entity is not None
    await entity.async_set_fan_mode("unknown")

    assert "Unsupported fan mode: unknown" in caplog.text
    assert mock_gateway.send_calls == 0


async def test_fan_modes_are_mapped(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test the gateway's fan modes are offered under their HA names."""
    await setup_integration(hass, mock_config_entry)

    mock_gateway.push_status(build_status(fan_mode=StatusFanMode.MIDHIGH))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_FAN_MODE] == FAN_MEDIUM_HIGH
    # The two intermediate speeds used to reach the user under the names the
    # protocol uses on the wire, because they had no mapping.
    assert state.attributes[ATTR_FAN_MODES] == ALL_FAN_MODES


async def test_device_address_is_used_for_the_entity(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test a gateway with more than one device gets one entity each."""
    mock_gateway.discovery_result = [DEVICE_ADDRESS, (1, 2)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is not None
    assert hass.states.get("climate.ac_1_2") is not None
