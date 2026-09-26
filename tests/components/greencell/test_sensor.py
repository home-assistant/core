"""Real integration tests for Greencell EVSE sensors."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.greencell.const import GREENCELL_HABU_DEN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import slugify

from .conftest import (
    TEST_CURRENT_PAYLOAD_3PHASE,
    TEST_CURRENT_PAYLOAD_SINGLE,
    TEST_CURRENT_TOPIC,
    TEST_POWER_PAYLOAD_CHARGING,
    TEST_POWER_TOPIC,
    TEST_SERIAL_NUMBER,
    TEST_STATUS_PAYLOAD_CHARGING,
    TEST_STATUS_PAYLOAD_CONNECTED,
    TEST_STATUS_PAYLOAD_ERROR,
    TEST_STATUS_PAYLOAD_ERROR_CAR,
    TEST_STATUS_PAYLOAD_FINISHED,
    TEST_STATUS_PAYLOAD_IDLE,
    TEST_STATUS_PAYLOAD_UNAVAILABLE,
    TEST_STATUS_PAYLOAD_WAITING_FOR_CAR,
    TEST_STATUS_TOPIC,
    TEST_VOLTAGE_PAYLOAD_NORMAL,
    TEST_VOLTAGE_PAYLOAD_SINGLE,
    TEST_VOLTAGE_TOPIC,
)

from tests.common import MockConfigEntry, async_fire_mqtt_message


async def test_sensor_states_and_snapshots(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Verify all sensor states including single-phase charging and snapshots."""
    prefix = f"sensor.{slugify(f'{GREENCELL_HABU_DEN} {TEST_SERIAL_NUMBER}')}"

    curr_l1 = f"{prefix}_current_phase_l1"
    curr_l2 = f"{prefix}_current_phase_l2"
    volt_l1 = f"{prefix}_voltage_phase_l1"
    volt_l2 = f"{prefix}_voltage_phase_l2"

    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_3PHASE)
    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, TEST_VOLTAGE_PAYLOAD_NORMAL)
    await hass.async_block_till_done()

    for eid in (curr_l1, curr_l2, volt_l1, volt_l2):
        await async_update_entity(hass, eid)

    assert hass.states.get(curr_l1).state == "2.0"
    assert hass.states.get(curr_l2).state == "2.5"
    assert hass.states.get(volt_l1).state == "230.0"

    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_SINGLE)
    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, TEST_VOLTAGE_PAYLOAD_SINGLE)
    await hass.async_block_till_done()

    for eid in (curr_l1, curr_l2, volt_l1, volt_l2):
        await async_update_entity(hass, eid)

    assert hass.states.get(curr_l1).state == "16.5"
    assert hass.states.get(curr_l2).state == "0.0"
    assert hass.states.get(volt_l2).state == "0.0"

    async_fire_mqtt_message(hass, TEST_POWER_TOPIC, TEST_POWER_PAYLOAD_CHARGING)
    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_CHARGING)
    await hass.async_block_till_done()

    await async_update_entity(hass, f"{prefix}_status")
    assert hass.states.get(curr_l1) == snapshot

    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_UNAVAILABLE)
    await hass.async_block_till_done()

    await async_update_entity(hass, curr_l1)
    assert hass.states.get(curr_l1).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("payload", "expected_state"),
    [
        (TEST_STATUS_PAYLOAD_IDLE, "idle"),
        (TEST_STATUS_PAYLOAD_CONNECTED, "connected"),
        (TEST_STATUS_PAYLOAD_CHARGING, "charging"),
        (TEST_STATUS_PAYLOAD_FINISHED, "finished"),
        (TEST_STATUS_PAYLOAD_ERROR, "error_evse"),
        (TEST_STATUS_PAYLOAD_WAITING_FOR_CAR, "waiting_for_car"),
        (TEST_STATUS_PAYLOAD_ERROR_CAR, "error_car"),
    ],
)
async def test_sensor_status_states(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    payload: bytes,
    expected_state: str,
) -> None:
    """Verify all possible status states using parametrization."""
    prefix = f"sensor.{slugify(f'{GREENCELL_HABU_DEN} {TEST_SERIAL_NUMBER}')}"
    status_id = f"{prefix}_status"

    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, payload)
    await hass.async_block_till_done()

    await async_update_entity(hass, status_id)
    await hass.async_block_till_done()

    state = hass.states.get(status_id)
    assert state is not None
    assert state.state == expected_state


async def test_sensor_availability_and_errors(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Verify availability logic (UNAVAILABLE) and payload error handling."""
    prefix = f"sensor.{slugify(f'{GREENCELL_HABU_DEN} {TEST_SERIAL_NUMBER}')}"
    curr_l1 = f"{prefix}_current_phase_l1"

    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_UNAVAILABLE)
    await hass.async_block_till_done()

    await async_update_entity(hass, curr_l1)
    state = hass.states.get(curr_l1)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
