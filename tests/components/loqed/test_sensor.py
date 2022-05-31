"""Tests the sensor platform of the Loqed integration."""
from homeassistant.components.loqed import LoqedDataCoordinator
from homeassistant.components.loqed.const import CONF_COORDINATOR, DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_battery_sensor(
    hass: HomeAssistant,
    integration: MockConfigEntry,
) -> None:
    """Test the battery sensor."""
    entity_id = "sensor.loqed_battery_status"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "78"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.BATTERY
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT


async def test_wifi_stength_sensor(
    hass: HomeAssistant,
    integration: MockConfigEntry,
) -> None:
    """Test the wifi signal strength sensor."""
    entity_id = "sensor.loqed_wifi_signal_strength"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "73"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SIGNAL_STRENGTH
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == SIGNAL_STRENGTH_DECIBELS
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT


async def test_ble_strength_sensor(
    hass: HomeAssistant,
    integration: MockConfigEntry,
) -> None:
    """Test the bluetooth signal strength sensor."""
    entity_id = "sensor.loqed_bluetooth_signal_strength"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "20"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SIGNAL_STRENGTH
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == SIGNAL_STRENGTH_DECIBELS
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT


async def test_battery_sensor_update(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Tests the sensor responding to a coordinator update."""

    entity_id = "sensor.loqed_battery_status"

    coordinator: LoqedDataCoordinator = hass.data[DOMAIN][integration.entry_id][
        CONF_COORDINATOR
    ]
    coordinator.async_set_updated_data({"battery_percentage": 99})

    state = hass.states.get(entity_id)
    assert state.state == "99"
