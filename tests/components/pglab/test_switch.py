"""The tests for the PG LAB Electronics switch."""

from datetime import timedelta

from homeassistant import config_entries
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .test_common import get_device_discovery_payload, send_discovery_message

from tests.common import async_fire_mqtt_message, async_fire_time_changed
from tests.typing import MqttMockHAClient


async def call_service(hass: HomeAssistant, entity_id, service, **kwargs):
    """Call a service."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **kwargs},
        blocking=True,
    )


async def test_available_relay(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Check if relay are properly created when two E-Relay boards are connected."""

    payload = get_device_discovery_payload(
        number_of_shutters=0,
        number_of_boards=2,
    )

    await send_discovery_message(hass, payload)

    for i in range(16):
        state = hass.states.get(f"switch.test_relay_{i}")
        assert state.state == STATE_UNKNOWN
        assert not state.attributes.get(ATTR_ASSUMED_STATE)


async def test_change_state_via_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Test state update via MQTT."""

    payload = get_device_discovery_payload(
        number_of_shutters=0,
        number_of_boards=1,
    )

    await send_discovery_message(hass, payload)

    # Simulate response from the device
    state = hass.states.get("switch.test_relay_0")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn relay OFF
    async_fire_mqtt_message(hass, "pglab/test/relay/0/state", "OFF")
    await hass.async_block_till_done()
    state = hass.states.get("switch.test_relay_0")
    assert not state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.state == STATE_OFF

    # Turn relay ON
    async_fire_mqtt_message(hass, "pglab/test/relay/0/state", "ON")
    await hass.async_block_till_done()
    state = hass.states.get("switch.test_relay_0")
    assert state.state == STATE_ON

    # Turn relay OFF
    async_fire_mqtt_message(hass, "pglab/test/relay/0/state", "OFF")
    await hass.async_block_till_done()
    state = hass.states.get("switch.test_relay_0")
    assert state.state == STATE_OFF

    # Turn relay ON
    async_fire_mqtt_message(hass, "pglab/test/relay/0/state", "ON")
    await hass.async_block_till_done()
    state = hass.states.get("switch.test_relay_0")
    assert state.state == STATE_ON


async def test_mqtt_state_by_calling_service(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Calling service to turn ON/OFF relay and check mqtt state."""

    payload = get_device_discovery_payload(
        number_of_shutters=0,
        number_of_boards=1,
    )

    await send_discovery_message(hass, payload)

    # Turn relay ON
    await call_service(hass, "switch.test_relay_0", SERVICE_TURN_ON)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/relay/0/set", "ON", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Turn relay OFF
    await call_service(hass, "switch.test_relay_0", SERVICE_TURN_OFF)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/relay/0/set", "OFF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Turn relay ON
    await call_service(hass, "switch.test_relay_3", SERVICE_TURN_ON)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/relay/3/set", "ON", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Turn relay OFF
    await call_service(hass, "switch.test_relay_3", SERVICE_TURN_OFF)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/relay/3/set", "OFF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_discovery_update(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Update discovery message and  check if relay are property updated."""

    payload = get_device_discovery_payload(
        device_name="first_test",
        number_of_shutters=0,
        number_of_boards=1,
    )

    await send_discovery_message(hass, payload)

    # test the available relay in the first configuration
    for i in range(8):
        state = hass.states.get(f"switch.first_test_relay_{i}")
        assert state.state == STATE_UNKNOWN
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # prepare a new message ... the same device but renamed
    # and with different relay configuration
    payload = get_device_discovery_payload(
        device_name="second_test",
        number_of_shutters=0,
        number_of_boards=2,
    )

    await send_discovery_message(hass, payload)

    # be sure that old relay are been removed
    for i in range(8):
        assert not hass.states.get(f"switch.first_test_relay_{i}")

    # check new relay
    for i in range(16):
        state = hass.states.get(f"switch.second_test_relay_{i}")
        assert state.state == STATE_UNKNOWN
        assert not state.attributes.get(ATTR_ASSUMED_STATE)


async def test_disable_entity_state_change_via_mqtt(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mqtt_mock: MqttMockHAClient,
    setup_pglab,
) -> None:
    """Test state update via MQTT of disable entity."""

    payload = get_device_discovery_payload(
        number_of_shutters=0,
        number_of_boards=1,
    )

    await send_discovery_message(hass, payload)

    # Be sure that the entity relay_0 is available
    state = hass.states.get("switch.test_relay_0")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Disable entity relay_0
    new_status = entity_registry.async_update_entity(
        "switch.test_relay_0", disabled_by=er.RegistryEntryDisabler.USER
    )

    # Be sure that the entity is disabled
    assert new_status.disabled is True

    # Try to change the state of the disabled relay_0
    async_fire_mqtt_message(hass, "pglab/test/relay/0/state", "ON")
    await hass.async_block_till_done()

    # Enable entity relay_0
    new_status = entity_registry.async_update_entity(
        "switch.test_relay_0", disabled_by=None
    )

    # Be sure that the entity is enabled
    assert new_status.disabled is False

    async_fire_time_changed(
        hass,
        dt_util.utcnow()
        + timedelta(seconds=config_entries.RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # Re-send the discovery message
    await send_discovery_message(hass, payload)

    # Be sure that the state is not changed
    state = hass.states.get("switch.test_relay_0")
    assert state.state == STATE_UNKNOWN

    # Try again to change the state of the disabled relay_0
    async_fire_mqtt_message(hass, "pglab/test/relay/0/state", "ON")
    await hass.async_block_till_done()

    # Be sure that the state is been updated
    state = hass.states.get("switch.test_relay_0")
    assert state.state == STATE_ON
