"""Tests for DSMR Reader sensor."""

from unittest.mock import MagicMock, patch

from homeassistant.components.dsmr_reader.const import DOMAIN
from homeassistant.components.dsmr_reader.definitions import (
    DSMRReaderSensorEntityDescription,
)
from homeassistant.components.dsmr_reader.sensor import DSMRSensor
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@patch("homeassistant.components.dsmr_reader.sensor.mqtt.async_subscribe")
async def test_dsmr_sensor_async_added_to_hass(
    mock_mqtt_subscribe, hass: HomeAssistant
) -> None:
    """Test the async_added_to_hass method of the DSMRSensor class."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        options={},
        entry_id="TEST_ENTRY_ID",
        unique_id="UNIQUE_TEST_ID",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dsmr_reader.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    mock_mqtt_subscribe.side_effect = lambda hass, key, callback, qos: callback(message)
    message = MagicMock()

    # All three sensor tests are done in one test function
    # Test when message payload is empty
    message.payload = ""
    description = DSMRReaderSensorEntityDescription(
        key="DSMR_TEST_KEY",
        name="DSMR_TEST_NAME",
        state=None,
    )
    sensor = DSMRSensor(description, config_entry)
    sensor.hass = hass
    await sensor.async_added_to_hass()
    assert sensor.native_value is None

    # Test if entity_description.state is not None
    message.payload = "test_payload"
    description = DSMRReaderSensorEntityDescription(
        key="DSMR_TEST_KEY",
        name="DSMR_TEST_NAME",
        state=lambda x: x,
    )
    sensor = DSMRSensor(description, config_entry)
    sensor.hass = hass
    await sensor.async_added_to_hass()
    assert sensor.native_value == message.payload

    # Test when entity_description.state is None
    description = DSMRReaderSensorEntityDescription(
        key="DSMR_TEST_KEY",
        name="DSMR_TEST_NAME",
        state=None,
    )
    sensor = DSMRSensor(description, config_entry)
    sensor.hass = hass
    await sensor.async_added_to_hass()
    assert sensor.native_value == message.payload
