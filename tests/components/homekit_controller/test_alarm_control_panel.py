"""Basic checks for HomeKitalarm_control_panel."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import get_next_aid, setup_test_component


def create_security_system_service(accessory):
    """Define a security-system characteristics as per page 219 of HAP spec."""
    service = accessory.add_service(ServicesTypes.SECURITY_SYSTEM)

    cur_state = service.add_char(CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT)
    cur_state.value = 0

    targ_state = service.add_char(CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET)
    targ_state.value = 0

    # According to the spec, a battery-level characteristic is normally
    # part of a separate service. However as the code was written (which
    # predates this test) the battery level would have to be part of the lock
    # service as it is here.
    targ_state = service.add_char(CharacteristicsTypes.BATTERY_LEVEL)
    targ_state.value = 50


async def test_switch_change_alarm_state(hass: HomeAssistant, utcnow) -> None:
    """Test that we can turn a HomeKit alarm on and off again."""
    helper = await setup_test_component(hass, create_security_system_service)

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_home",
        {"entity_id": "alarm_control_panel.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.SECURITY_SYSTEM,
        {
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET: 0,
        },
    )

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_away",
        {"entity_id": "alarm_control_panel.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.SECURITY_SYSTEM,
        {
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET: 1,
        },
    )

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_night",
        {"entity_id": "alarm_control_panel.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.SECURITY_SYSTEM,
        {
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET: 2,
        },
    )

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_disarm",
        {"entity_id": "alarm_control_panel.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.SECURITY_SYSTEM,
        {
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET: 3,
        },
    )


async def test_switch_read_alarm_state(hass: HomeAssistant, utcnow) -> None:
    """Test that we can read the state of a HomeKit alarm accessory."""
    helper = await setup_test_component(hass, create_security_system_service)

    await helper.async_update(
        ServicesTypes.SECURITY_SYSTEM,
        {CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT: 0},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "armed_home"
    assert state.attributes["battery_level"] == 50

    await helper.async_update(
        ServicesTypes.SECURITY_SYSTEM,
        {CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT: 1},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "armed_away"

    await helper.async_update(
        ServicesTypes.SECURITY_SYSTEM,
        {CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT: 2},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "armed_night"

    await helper.async_update(
        ServicesTypes.SECURITY_SYSTEM,
        {CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT: 3},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "disarmed"

    await helper.async_update(
        ServicesTypes.SECURITY_SYSTEM,
        {CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT: 4},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "triggered"


async def test_migrate_unique_id(hass: HomeAssistant, utcnow) -> None:
    """Test a we can migrate a alarm_control_panel unique id."""
    entity_registry = er.async_get(hass)
    aid = get_next_aid()
    alarm_control_panel_entry = entity_registry.async_get_or_create(
        "alarm_control_panel",
        "homekit_controller",
        f"homekit-00:00:00:00:00:00-{aid}-8",
    )
    await setup_test_component(hass, create_security_system_service)

    assert (
        entity_registry.async_get(alarm_control_panel_entry.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8"
    )
