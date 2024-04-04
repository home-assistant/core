"""Test for the SmartThings fan platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""

from pysmartthings import Attribute, Capability

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as FAN_DOMAIN,
    FanEntityFeature,
)
from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


async def test_entity_state(hass: HomeAssistant, device_factory) -> None:
    """Tests the state attributes properly match the fan types."""
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "on", Attribute.fan_speed: 2},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])

    # Dimmer 1
    state = hass.states.get("fan.fan_1")
    assert state.state == "on"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == FanEntityFeature.SET_SPEED
    assert state.attributes[ATTR_PERCENTAGE] == 66


async def test_entity_and_device_attributes(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={
            Attribute.switch: "on",
            Attribute.fan_speed: 2,
            Attribute.mnmo: "123",
            Attribute.mnmn: "Generic manufacturer",
            Attribute.mnhw: "v4.56",
            Attribute.mnfv: "v7.89",
        },
    )
    # Act
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Assert
    entry = entity_registry.async_get("fan.fan_1")
    assert entry
    assert entry.unique_id == device.device_id

    entry = device_registry.async_get_device(identifiers={(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == "123"
    assert entry.manufacturer == "Generic manufacturer"
    assert entry.hw_version == "v4.56"
    assert entry.sw_version == "v7.89"


# Setup platform tests with varying capabilities
async def test_setup_mode_capability(hass: HomeAssistant, device_factory) -> None:
    """Test setting up a fan with only the mode capability."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.air_conditioner_fan_mode],
        status={
            Attribute.switch: "off",
            Attribute.fan_mode: "high",
            Attribute.supported_ac_fan_modes: ["high", "low", "medium"],
        },
    )

    await setup_platform(hass, FAN_DOMAIN, devices=[device])

    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == FanEntityFeature.PRESET_MODE
    assert state.attributes[ATTR_PRESET_MODE] == "high"
    assert state.attributes[ATTR_PRESET_MODES] == ["high", "low", "medium"]


async def test_setup_speed_capability(hass: HomeAssistant, device_factory) -> None:
    """Test setting up a fan with only the speed capability."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={
            Attribute.switch: "off",
            Attribute.fan_speed: 2,
        },
    )

    await setup_platform(hass, FAN_DOMAIN, devices=[device])

    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == FanEntityFeature.SET_SPEED
    assert state.attributes[ATTR_PERCENTAGE] == 66


async def test_setup_both_capabilities(hass: HomeAssistant, device_factory) -> None:
    """Test setting up a fan with both the mode and speed capability."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[
            Capability.switch,
            Capability.fan_speed,
            Capability.air_conditioner_fan_mode,
        ],
        status={
            Attribute.switch: "off",
            Attribute.fan_speed: 2,
            Attribute.fan_mode: "high",
            Attribute.supported_ac_fan_modes: ["high", "low", "medium"],
        },
    )

    await setup_platform(hass, FAN_DOMAIN, devices=[device])

    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
    )
    assert state.attributes[ATTR_PERCENTAGE] == 66
    assert state.attributes[ATTR_PRESET_MODE] == "high"
    assert state.attributes[ATTR_PRESET_MODES] == ["high", "low", "medium"]


# Speed Capability Tests


async def test_turn_off_speed_capability(hass: HomeAssistant, device_factory) -> None:
    """Test the fan turns of successfully."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "on", Attribute.fan_speed: 2},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.fan_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "off"


async def test_turn_on_speed_capability(hass: HomeAssistant, device_factory) -> None:
    """Test the fan turns of successfully."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan", "turn_on", {ATTR_ENTITY_ID: "fan.fan_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"


async def test_turn_on_with_speed_speed_capability(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the fan turns on to the specified speed."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan",
        "turn_on",
        {ATTR_ENTITY_ID: "fan.fan_1", ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"
    assert state.attributes[ATTR_PERCENTAGE] == 100


async def test_turn_off_with_speed_speed_capability(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the fan turns off with the speed."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "on", Attribute.fan_speed: 100},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {ATTR_ENTITY_ID: "fan.fan_1", ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "off"


async def test_set_percentage_speed_capability(
    hass: HomeAssistant, device_factory
) -> None:
    """Test setting to specific fan speed."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {ATTR_ENTITY_ID: "fan.fan_1", ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"
    assert state.attributes[ATTR_PERCENTAGE] == 100


async def test_update_from_signal_speed_capability(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the fan updates when receiving a signal."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    await device.switch_on(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"


async def test_unload_config_entry(hass: HomeAssistant, device_factory) -> None:
    """Test the fan is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    config_entry = await setup_platform(hass, FAN_DOMAIN, devices=[device])
    config_entry.mock_state(hass, ConfigEntryState.LOADED)
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "fan")
    # Assert
    assert hass.states.get("fan.fan_1").state == STATE_UNAVAILABLE


# Preset Mode Tests


async def test_turn_off_mode_capability(hass: HomeAssistant, device_factory) -> None:
    """Test the fan turns of successfully."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.air_conditioner_fan_mode],
        status={
            Attribute.switch: "on",
            Attribute.fan_mode: "high",
            Attribute.supported_ac_fan_modes: ["high", "low", "medium"],
        },
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.fan_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "off"
    assert state.attributes[ATTR_PRESET_MODE] == "high"


async def test_turn_on_mode_capability(hass: HomeAssistant, device_factory) -> None:
    """Test the fan turns of successfully."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.air_conditioner_fan_mode],
        status={
            Attribute.switch: "off",
            Attribute.fan_mode: "high",
            Attribute.supported_ac_fan_modes: ["high", "low", "medium"],
        },
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan", "turn_on", {ATTR_ENTITY_ID: "fan.fan_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"
    assert state.attributes[ATTR_PRESET_MODE] == "high"


async def test_update_from_signal_mode_capability(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the fan updates when receiving a signal."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.air_conditioner_fan_mode],
        status={
            Attribute.switch: "off",
            Attribute.fan_mode: "high",
            Attribute.supported_ac_fan_modes: ["high", "low", "medium"],
        },
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    await device.switch_on(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"


async def test_set_preset_mode_mode_capability(
    hass: HomeAssistant, device_factory
) -> None:
    """Test setting to specific fan mode."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.air_conditioner_fan_mode],
        status={
            Attribute.switch: "off",
            Attribute.fan_mode: "high",
            Attribute.supported_ac_fan_modes: ["high", "low", "medium"],
        },
    )

    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan",
        "set_preset_mode",
        {ATTR_ENTITY_ID: "fan.fan_1", ATTR_PRESET_MODE: "low"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "low"
