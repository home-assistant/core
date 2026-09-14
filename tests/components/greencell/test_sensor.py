"""Real integration tests for Greencell EVSE sensors."""

import logging

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.greencell.const import GREENCELL_HABU_DEN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import slugify

from .conftest import (
    TEST_CURRENT_PAYLOAD_3PHASE,
    TEST_CURRENT_PAYLOAD_SINGLE,
    TEST_CURRENT_TOPIC,
    TEST_DEVICE_STATE_PAYLOAD_EXECUTE,
    TEST_DEVICE_STATE_TOPIC,
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
    patch_device_ready,
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

    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_3PHASE)
    await hass.async_block_till_done()

    for eid in (curr_l1, curr_l2):
        await async_update_entity(hass, eid)

    assert hass.states.get(curr_l1).state == "2.0"
    assert hass.states.get(curr_l2).state == "2.5"

    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_SINGLE)
    await hass.async_block_till_done()

    for eid in (curr_l1, curr_l2):
        await async_update_entity(hass, eid)

    assert hass.states.get(curr_l1).state == "16.5"
    assert hass.states.get(curr_l2).state == "0.0"

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


async def test_log_when_unavailable(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Losing and regaining the device is logged exactly once per transition."""
    caplog.set_level(logging.INFO)

    for _ in range(2):
        async_fire_mqtt_message(
            hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_UNAVAILABLE
        )
    await hass.async_block_till_done()

    assert caplog.text.count(f"Device {TEST_SERIAL_NUMBER} is unavailable") == 1

    for _ in range(2):
        async_fire_mqtt_message(
            hass, TEST_DEVICE_STATE_TOPIC, TEST_DEVICE_STATE_PAYLOAD_EXECUTE
        )
    await hass.async_block_till_done()

    assert caplog.text.count(f"Device {TEST_SERIAL_NUMBER} is available again") == 1


async def test_voltage_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_integration: MockConfigEntry,
) -> None:
    """Voltage is diagnostic data, so the phase voltages are registered disabled."""
    prefix = f"sensor.{slugify(f'{GREENCELL_HABU_DEN} {TEST_SERIAL_NUMBER}')}"

    for phase in ("l1", "l2", "l3"):
        entity_id = f"{prefix}_voltage_phase_{phase}"
        assert hass.states.get(entity_id) is None
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_voltage_sensors_report_when_enabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_integration: MockConfigEntry,
) -> None:
    """Voltage sensors report their measurements once the user enables them."""
    prefix = f"sensor.{slugify(f'{GREENCELL_HABU_DEN} {TEST_SERIAL_NUMBER}')}"
    volt_l1 = f"{prefix}_voltage_phase_l1"
    volt_l2 = f"{prefix}_voltage_phase_l2"

    for entity_id in (volt_l1, volt_l2):
        entity_registry.async_update_entity(entity_id, disabled_by=None)

    with patch_device_ready():
        await hass.config_entries.async_reload(setup_integration.entry_id)
        await hass.async_block_till_done()

    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, TEST_VOLTAGE_PAYLOAD_NORMAL)
    await hass.async_block_till_done()

    for entity_id in (volt_l1, volt_l2):
        await async_update_entity(hass, entity_id)

    assert hass.states.get(volt_l1).state == "230.0"

    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, TEST_VOLTAGE_PAYLOAD_SINGLE)
    await hass.async_block_till_done()

    await async_update_entity(hass, volt_l2)
    assert hass.states.get(volt_l2).state == "0.0"
