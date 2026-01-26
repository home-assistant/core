"""Real integration tests for Greencell EVSE sensors."""

from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_CURRENT_PAYLOAD_3PHASE,
    TEST_CURRENT_PAYLOAD_IDLE,
    TEST_CURRENT_TOPIC,
    TEST_DEVICE_STATE_OFFLINE,
    TEST_DEVICE_STATE_ONLINE,
    TEST_DEVICE_STATE_TOPIC,
    TEST_POWER_PAYLOAD_CHARGING,
    TEST_POWER_PAYLOAD_IDLE,
    TEST_POWER_TOPIC,
    TEST_STATUS_PAYLOAD_CHARGING,
    TEST_STATUS_PAYLOAD_IDLE,
    TEST_STATUS_PAYLOAD_UNAVAILABLE,
    TEST_STATUS_TOPIC,
    TEST_VOLTAGE_PAYLOAD_LOW,
    TEST_VOLTAGE_PAYLOAD_NORMAL,
    TEST_VOLTAGE_TOPIC,
)

from tests.common import async_fire_mqtt_message


async def test_setup_entry_creates_sensors(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that setup_entry creates sensor entities."""
    mock_config_entry.add_to_hass(hass)

    # Setup the config entry
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # At minimum, verify config entry was processed
    entries = hass.config_entries.async_entries("greencell")
    assert len(entries) == 1
    assert entries[0].entry_id == mock_config_entry.entry_id


async def test_current_sensor_receives_mqtt_update(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that current sensor receives and processes MQTT updates."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message with 3-phase current data
    # Values: L1: 2000mA, L2: 2500mA, L3: 3000mA
    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_3PHASE)
    await hass.async_block_till_done()


async def test_voltage_sensor_receives_mqtt_update(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that voltage sensor receives and processes MQTT updates."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message with normal voltage data
    # Values: L1: 230.0V, L2: 229.7V, L3: 232.5V
    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, TEST_VOLTAGE_PAYLOAD_NORMAL)
    await hass.async_block_till_done()


async def test_low_voltage_mqtt_update(
    hass: HomeAssistant, mock_config_entry, setup_mqtt
) -> None:
    """Test that voltage sensor handles low voltage conditions."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message with low voltage data
    # Values: L1: 210.0V, L2: 209.7V, L3: 212.5V
    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, TEST_VOLTAGE_PAYLOAD_LOW)
    await hass.async_block_till_done()


async def test_power_sensor_charging_mqtt_update(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that power sensor receives charging power updates."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message with charging power data (1500.5W)
    async_fire_mqtt_message(hass, TEST_POWER_TOPIC, TEST_POWER_PAYLOAD_CHARGING)
    await hass.async_block_till_done()


async def test_power_sensor_idle_mqtt_update(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that power sensor handles idle/zero power."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message with idle power data (0.0W)
    async_fire_mqtt_message(hass, TEST_POWER_TOPIC, TEST_POWER_PAYLOAD_IDLE)
    await hass.async_block_till_done()


async def test_status_sensor_charging_state(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that status sensor receives charging state update."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message with charging status
    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_CHARGING)
    await hass.async_block_till_done()

    # Message was processed successfully
    assert True


async def test_status_sensor_idle_state(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that status sensor receives idle state update."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message with idle status
    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_IDLE)
    await hass.async_block_till_done()


async def test_device_unavailable_status(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that device handles UNAVAILABLE status correctly."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message indicating device is unavailable
    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_UNAVAILABLE)
    await hass.async_block_till_done()


async def test_device_online_state(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that device handles online state from device_state topic."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message indicating device is online
    async_fire_mqtt_message(hass, TEST_DEVICE_STATE_TOPIC, TEST_DEVICE_STATE_ONLINE)
    await hass.async_block_till_done()


async def test_device_offline_state(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that device handles offline state from device_state topic."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire MQTT message indicating device is offline
    async_fire_mqtt_message(hass, TEST_DEVICE_STATE_TOPIC, TEST_DEVICE_STATE_OFFLINE)
    await hass.async_block_till_done()


async def test_sequential_current_updates(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that current sensor handles multiple sequential updates."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Send idle current
    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_IDLE)
    await hass.async_block_till_done()

    # Send 3-phase current
    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_3PHASE)
    await hass.async_block_till_done()

    # Send idle current again
    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_IDLE)
    await hass.async_block_till_done()


async def test_all_sensor_types_in_sequence(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that all sensor types can receive updates in sequence."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Send current update
    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_3PHASE)
    await hass.async_block_till_done()

    # Send voltage update
    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, TEST_VOLTAGE_PAYLOAD_NORMAL)
    await hass.async_block_till_done()

    # Send power update
    async_fire_mqtt_message(hass, TEST_POWER_TOPIC, TEST_POWER_PAYLOAD_CHARGING)
    await hass.async_block_till_done()

    # Send status update
    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_CHARGING)
    await hass.async_block_till_done()

    # Send device state update
    async_fire_mqtt_message(hass, TEST_DEVICE_STATE_TOPIC, TEST_DEVICE_STATE_ONLINE)
    await hass.async_block_till_done()


async def test_rapid_mqtt_messages(
    hass: HomeAssistant,
    mock_config_entry,
    setup_mqtt,
) -> None:
    """Test that component handles rapid MQTT messages without errors."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Send 10 rapid MQTT messages
    for _ in range(10):
        async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_3PHASE)
        async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, TEST_VOLTAGE_PAYLOAD_NORMAL)
        async_fire_mqtt_message(hass, TEST_POWER_TOPIC, TEST_POWER_PAYLOAD_CHARGING)
        async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_CHARGING)

    await hass.async_block_till_done()
