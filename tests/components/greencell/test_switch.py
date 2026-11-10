"""Tests for the Greencell charging switch."""

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    snapshot_platform,
)
from pytest_homeassistant.typing import MqttMockHAClient
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    TEST_DEVICE_STATE_TOPIC,
    TEST_SERIAL_NUMBER,
    TEST_STATUS_PAYLOAD_CHARGING,
    TEST_STATUS_PAYLOAD_CONNECTED,
    TEST_STATUS_PAYLOAD_FINISHED,
    TEST_STATUS_PAYLOAD_IDLE,
    TEST_STATUS_PAYLOAD_UNAVAILABLE,
    TEST_STATUS_PAYLOAD_WAITING_FOR_CAR,
    TEST_STATUS_TOPIC,
)

SWITCH_ENTITY_ID = "switch.habu_den_evgc021a22750001zm0001_charging"
TEST_CMD_TOPIC = f"/greencell/evse/{TEST_SERIAL_NUMBER}/cmd"
TEST_DEVICE_STATE_PAYLOAD_READ = b'{"level": "READ"}'


@pytest.mark.parametrize("platforms", [[Platform.SWITCH]])
@pytest.mark.usefixtures("setup_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("payload", "expected_state"),
    [
        pytest.param(TEST_STATUS_PAYLOAD_CHARGING, STATE_ON, id="charging"),
        pytest.param(TEST_STATUS_PAYLOAD_WAITING_FOR_CAR, STATE_ON, id="waiting"),
        pytest.param(TEST_STATUS_PAYLOAD_CONNECTED, STATE_OFF, id="connected"),
        pytest.param(TEST_STATUS_PAYLOAD_FINISHED, STATE_OFF, id="finished"),
        pytest.param(TEST_STATUS_PAYLOAD_IDLE, STATE_OFF, id="idle"),
        pytest.param(TEST_STATUS_PAYLOAD_UNAVAILABLE, STATE_UNAVAILABLE, id="offline"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_switch_state_follows_status(
    hass: HomeAssistant,
    payload: bytes,
    expected_state: str,
) -> None:
    """The switch state mirrors the charging status reported by the device."""
    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, payload)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_payload"),
    [
        pytest.param(SERVICE_TURN_ON, '{"name": "START"}', id="start"),
        pytest.param(SERVICE_TURN_OFF, '{"name": "STOP"}', id="stop"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_switch_sends_command(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    service: str,
    expected_payload: str,
) -> None:
    """Turning the switch on or off publishes the matching command."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        TEST_CMD_TOPIC, expected_payload, 0, False, message_expiry_interval=None
    )


@pytest.mark.usefixtures("setup_integration")
async def test_switch_rejects_command_without_execute_access(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Commands are refused when the device only grants read access."""
    async_fire_mqtt_message(
        hass, TEST_DEVICE_STATE_TOPIC, TEST_DEVICE_STATE_PAYLOAD_READ
    )
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="does not allow Home Assistant"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )

    mqtt_mock.async_publish.assert_not_called()
