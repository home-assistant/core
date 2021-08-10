"""Basic checks for HomeKitSwitch."""

from aiohomekit.model.characteristics import (
    CharacteristicsTypes,
    InUseValues,
    IsConfiguredValues,
)
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import setup_test_component


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


async def test_switch_change_outlet_state(hass, utcnow):
    """Test that we can turn a HomeKit outlet on and off again."""
    helper = await setup_test_component(hass, create_switch_service)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.testdevice"}, blocking=True
    )
    assert helper.characteristics[("outlet", "on")].value == 1

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.testdevice"}, blocking=True
    )
    assert helper.characteristics[("outlet", "on")].value == 0


async def test_switch_read_outlet_state(hass, utcnow):
    """Test that we can read the state of a HomeKit outlet accessory."""
    helper = await setup_test_component(hass, create_switch_service)

    # Initial state is that the switch is off and the outlet isn't in use
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == "off"
    assert switch_1.attributes["outlet_in_use"] is False

    # Simulate that someone switched on the device in the real world not via HA
    helper.characteristics[("outlet", "on")].set_value(True)
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == "on"
    assert switch_1.attributes["outlet_in_use"] is False

    # Simulate that device switched off in the real world not via HA
    helper.characteristics[("outlet", "on")].set_value(False)
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == "off"

    # Simulate that someone plugged something into the device
    helper.characteristics[("outlet", "outlet-in-use")].value = True
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == "off"
    assert switch_1.attributes["outlet_in_use"] is True


async def test_valve_change_active_state(hass, utcnow):
    """Test that we can turn a valve on and off again."""
    helper = await setup_test_component(hass, create_valve_service)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.testdevice"}, blocking=True
    )
    assert helper.characteristics[("valve", "active")].value == 1

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.testdevice"}, blocking=True
    )
    assert helper.characteristics[("valve", "active")].value == 0


async def test_valve_read_state(hass, utcnow):
    """Test that we can read the state of a valve accessory."""
    helper = await setup_test_component(hass, create_valve_service)

    # Initial state is that the switch is off and the outlet isn't in use
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == "off"
    assert switch_1.attributes["in_use"] is True
    assert switch_1.attributes["is_configured"] is True
    assert switch_1.attributes["remaining_duration"] == 99

    # Simulate that someone switched on the device in the real world not via HA
    helper.characteristics[("valve", "active")].set_value(True)
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == "on"

    # Simulate that someone configured the device in the real world not via HA
    helper.characteristics[
        ("valve", "is-configured")
    ].value = IsConfiguredValues.NOT_CONFIGURED
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.attributes["is_configured"] is False

    # Simulate that someone using the device in the real world not via HA
    helper.characteristics[("valve", "in-use")].value = InUseValues.NOT_IN_USE
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.attributes["in_use"] is False
