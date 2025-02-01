"""Test for the SmartThings switch platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""

from pysmartthings import Attribute, Capability

from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


async def test_entity_and_device_attributes(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_factory,
) -> None:
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory(
        "Switch_1",
        [Capability.switch],
        {
            Attribute.switch: "on",
            Attribute.mnmo: "123",
            Attribute.mnmn: "Generic manufacturer",
            Attribute.mnhw: "v4.56",
            Attribute.mnfv: "v7.89",
        },
    )
    # Act
    await setup_platform(hass, SWITCH_DOMAIN, devices=[device])
    # Assert
    entry = entity_registry.async_get("switch.switch_1")
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


async def test_turn_off(hass: HomeAssistant, device_factory) -> None:
    """Test the switch turns of successfully."""
    # Arrange
    device = device_factory("Switch_1", [Capability.switch], {Attribute.switch: "on"})
    await setup_platform(hass, SWITCH_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.switch_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("switch.switch_1")
    assert state is not None
    assert state.state == "off"


async def test_turn_on(hass: HomeAssistant, device_factory) -> None:
    """Test the switch turns of successfully."""
    # Arrange
    device = device_factory(
        "Switch_1",
        [Capability.switch, Capability.power_meter, Capability.energy_meter],
        {Attribute.switch: "off", Attribute.power: 355, Attribute.energy: 11.422},
    )
    await setup_platform(hass, SWITCH_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.switch_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("switch.switch_1")
    assert state is not None
    assert state.state == "on"


async def test_update_from_signal(hass: HomeAssistant, device_factory) -> None:
    """Test the switch updates when receiving a signal."""
    # Arrange
    device = device_factory("Switch_1", [Capability.switch], {Attribute.switch: "off"})
    await setup_platform(hass, SWITCH_DOMAIN, devices=[device])
    await device.switch_on(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("switch.switch_1")
    assert state is not None
    assert state.state == "on"


async def test_unload_config_entry(hass: HomeAssistant, device_factory) -> None:
    """Test the switch is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory("Switch 1", [Capability.switch], {Attribute.switch: "on"})
    config_entry = await setup_platform(hass, SWITCH_DOMAIN, devices=[device])
    config_entry.mock_state(hass, ConfigEntryState.LOADED)
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "switch")
    # Assert
    assert hass.states.get("switch.switch_1").state == STATE_UNAVAILABLE
