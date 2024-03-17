"""Basic checks for HomeKitSwitch."""

from aiohomekit.model.characteristics import (
    CharacteristicsTypes,
    InUseValues,
    IsConfiguredValues,
)
from aiohomekit.model.services import ServicesTypes

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import get_next_aid, setup_test_component


def create_switch_service(accessory):
    """Define outlet characteristics."""
    service = accessory.add_service(ServicesTypes.OUTLET)

    on_char = service.add_char(CharacteristicsTypes.ON)
    on_char.value = False

    outlet_in_use = service.add_char(CharacteristicsTypes.OUTLET_IN_USE)
    outlet_in_use.value = False


def create_valve_service(accessory):
    """Define valve characteristics."""
    service = accessory.add_service(ServicesTypes.VALVE)

    on_char = service.add_char(CharacteristicsTypes.ACTIVE)
    on_char.value = False

    in_use = service.add_char(CharacteristicsTypes.IN_USE)
    in_use.value = InUseValues.IN_USE

    configured = service.add_char(CharacteristicsTypes.IS_CONFIGURED)
    configured.value = IsConfiguredValues.CONFIGURED

    remaining = service.add_char(CharacteristicsTypes.REMAINING_DURATION)
    remaining.value = 99


def create_char_switch_service(accessory):
    """Define swtch characteristics."""
    service = accessory.add_service(ServicesTypes.OUTLET)

    on_char = service.add_char(CharacteristicsTypes.VENDOR_AQARA_PAIRING_MODE)
    on_char.perms.append("ev")
    on_char.value = False


async def test_switch_change_outlet_state(hass: HomeAssistant) -> None:
    """Test that we can turn a HomeKit outlet on and off again."""
    helper = await setup_test_component(hass, create_switch_service)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.testdevice"}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.OUTLET,
        {
            CharacteristicsTypes.ON: 1,
        },
    )

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.testdevice"}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.OUTLET,
        {
            CharacteristicsTypes.ON: 0,
        },
    )


async def test_switch_read_outlet_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit outlet accessory."""
    helper = await setup_test_component(hass, create_switch_service)

    # Initial state is that the switch is off and the outlet isn't in use
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == "off"
    assert switch_1.attributes["outlet_in_use"] is False

    # Simulate that someone switched on the device in the real world not via HA
    switch_1 = await helper.async_update(
        ServicesTypes.OUTLET,
        {CharacteristicsTypes.ON: True},
    )
    assert switch_1.state == "on"
    assert switch_1.attributes["outlet_in_use"] is False

    # Simulate that device switched off in the real world not via HA
    switch_1 = await helper.async_update(
        ServicesTypes.OUTLET,
        {CharacteristicsTypes.ON: False},
    )
    assert switch_1.state == "off"

    # Simulate that someone plugged something into the device
    switch_1 = await helper.async_update(
        ServicesTypes.OUTLET,
        {CharacteristicsTypes.OUTLET_IN_USE: True},
    )
    assert switch_1.state == "off"
    assert switch_1.attributes["outlet_in_use"] is True


async def test_valve_change_active_state(hass: HomeAssistant) -> None:
    """Test that we can turn a valve on and off again."""
    helper = await setup_test_component(hass, create_valve_service)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.testdevice"}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.VALVE,
        {
            CharacteristicsTypes.ACTIVE: 1,
        },
    )

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.testdevice"}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.VALVE,
        {
            CharacteristicsTypes.ACTIVE: 0,
        },
    )


async def test_valve_read_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a valve accessory."""
    helper = await setup_test_component(hass, create_valve_service)

    # Initial state is that the switch is off and the outlet isn't in use
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == "off"
    assert switch_1.attributes["in_use"] is True
    assert switch_1.attributes["is_configured"] is True
    assert switch_1.attributes["remaining_duration"] == 99

    # Simulate that someone switched on the device in the real world not via HA
    switch_1 = await helper.async_update(
        ServicesTypes.VALVE,
        {CharacteristicsTypes.ACTIVE: True},
    )
    assert switch_1.state == "on"

    # Simulate that someone configured the device in the real world not via HA
    switch_1 = await helper.async_update(
        ServicesTypes.VALVE,
        {CharacteristicsTypes.IS_CONFIGURED: IsConfiguredValues.NOT_CONFIGURED},
    )
    assert switch_1.attributes["is_configured"] is False

    # Simulate that someone using the device in the real world not via HA
    switch_1 = await helper.async_update(
        ServicesTypes.VALVE,
        {CharacteristicsTypes.IN_USE: InUseValues.NOT_IN_USE},
    )
    assert switch_1.attributes["in_use"] is False


async def test_char_switch_change_state(hass: HomeAssistant) -> None:
    """Test that we can turn a characteristic on and off again."""
    helper = await setup_test_component(
        hass, create_char_switch_service, suffix="pairing_mode"
    )

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.testdevice_pairing_mode"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.OUTLET,
        {
            CharacteristicsTypes.VENDOR_AQARA_PAIRING_MODE: True,
        },
    )

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.testdevice_pairing_mode"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.OUTLET,
        {
            CharacteristicsTypes.VENDOR_AQARA_PAIRING_MODE: False,
        },
    )


async def test_char_switch_read_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit characteristic switch."""
    helper = await setup_test_component(
        hass, create_char_switch_service, suffix="pairing_mode"
    )

    # Simulate that someone switched on the device in the real world not via HA
    switch_1 = await helper.async_update(
        ServicesTypes.OUTLET,
        {CharacteristicsTypes.VENDOR_AQARA_PAIRING_MODE: True},
    )
    assert switch_1.state == "on"

    # Simulate that device switched off in the real world not via HA
    switch_1 = await helper.async_update(
        ServicesTypes.OUTLET,
        {CharacteristicsTypes.VENDOR_AQARA_PAIRING_MODE: False},
    )
    assert switch_1.state == "off"


async def test_migrate_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a we can migrate a switch unique id."""
    aid = get_next_aid()
    switch_entry = entity_registry.async_get_or_create(
        "switch",
        "homekit_controller",
        f"homekit-00:00:00:00:00:00-{aid}-8",
    )
    switch_entry_2 = entity_registry.async_get_or_create(
        "switch",
        "homekit_controller",
        f"homekit-0001-aid:{aid}-sid:8-cid:9",
    )
    await setup_test_component(hass, create_char_switch_service, suffix="pairing_mode")

    assert (
        entity_registry.async_get(switch_entry.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8"
    )

    assert (
        entity_registry.async_get(switch_entry_2.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8_9"
    )
