"""Tests for DSMR Reader sensor."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_mqtt_message
from pytest_homeassistant.typing import MqttMockHAClient

from homeassistant.components.dsmr_reader.const import DOMAIN
from homeassistant.components.dsmr_reader.definitions import (
    DSMRReaderSensorEntityDescription,
)
from homeassistant.components.dsmr_reader.sensor import DSMRSensor
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir


async def test_dsmr_sensor_mqtt(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test the DSMRSensor class, via an emluated MQTT message."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        options={},
        entry_id="TEST_ENTRY_ID",
        unique_id="UNIQUE_TEST_ID",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    electricity_delivered_1 = "sensor.dsmr_reading_electricity_delivered_1"
    assert hass.states.get(electricity_delivered_1).state == STATE_UNKNOWN

    electricity_delivered_2 = "sensor.dsmr_reading_electricity_delivered_2"
    assert hass.states.get(electricity_delivered_2).state == STATE_UNKNOWN

    # Test if the payload is empty
    async_fire_mqtt_message(hass, "dsmr/reading/electricity_delivered_1", "")
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "dsmr/reading/electricity_delivered_2", "")
    await hass.async_block_till_done()

    assert hass.states.get(electricity_delivered_1).state == STATE_UNKNOWN
    assert hass.states.get(electricity_delivered_2).state == STATE_UNKNOWN

    # Test if the payload is not empty
    async_fire_mqtt_message(hass, "dsmr/reading/electricity_delivered_1", "1050.39")
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "dsmr/reading/electricity_delivered_2", "2001.12")
    await hass.async_block_till_done()

    assert hass.states.get(electricity_delivered_1).state == "1050.39"
    assert hass.states.get(electricity_delivered_2).state == "2001.12"

    # Create a test entity to ensure the entity_description.state is not None
    description = DSMRReaderSensorEntityDescription(
        key="DSMR_TEST_KEY",
        name="DSMR_TEST_NAME",
        state=lambda x: x,
    )
    sensor = DSMRSensor(description, config_entry)
    sensor.hass = hass
    await sensor.async_added_to_hass()
    async_fire_mqtt_message(hass, "DSMR_TEST_KEY", "192.8")
    await hass.async_block_till_done()
    assert sensor.native_value == "192.8"


@pytest.mark.usefixtures("mqtt_mock")
async def test_cannot_subscribe_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an issue linked to the entry is created when subscribing fails."""
    config_entry = MockConfigEntry(domain=DOMAIN, title=DOMAIN)
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dsmr_reader.sensor.mqtt.async_subscribe",
        side_effect=HomeAssistantError,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    issue_id = "cannot_subscribe_mqtt_topic_dsmr/reading/electricity_delivered_1"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == config_entry.entry_id

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
