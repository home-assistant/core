"""Test the Silla Prism setup."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.silla_prism.const import DOMAIN, OFFLINE_TIMEOUT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import fire_burst, setup_integration
from .const import BASE_TOPIC, HELLO_PAYLOAD, HELLO_TOPIC, SERIAL

from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
)
from tests.typing import MqttMockHAClient


async def test_setup_and_unload(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a config entry sets up, registers a device, and unloads."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, BASE_TOPIC), mock_config_entry.entry_id
    )
    assert device is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_mqtt_unavailable(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when the MQTT client is unavailable."""
    with patch(
        "homeassistant.components.silla_prism.coordinator.async_wait_for_mqtt_client",
        return_value=False,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_hello_updates_device_info(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a hello announcement enriches the device registry."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    async_fire_mqtt_message(hass, HELLO_TOPIC, HELLO_PAYLOAD)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, BASE_TOPIC), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.serial_number == SERIAL
    assert device.sw_version == "3.2.77"


POWER_ENTITY_ID = "sensor.silla_prism_power"


async def test_offline_and_back_online(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entities go unavailable when Prism is silent, and recover."""
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])
    await fire_burst(hass)
    assert hass.states.get(POWER_ENTITY_ID).state == "1760.0"

    # Any Prism message restarts the countdown.
    freezer.tick(OFFLINE_TIMEOUT / 2)
    async_fire_mqtt_message(hass, "prism/1/volt", "235.0")
    freezer.tick(OFFLINE_TIMEOUT / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "1760.0"

    freezer.tick(OFFLINE_TIMEOUT / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == STATE_UNAVAILABLE
    assert "No message received from Prism on prism for 150 seconds" in caplog.text

    # A message that does not change the status still proves Prism is alive.
    async_fire_mqtt_message(hass, HELLO_TOPIC, HELLO_PAYLOAD)
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "1760.0"
    assert "Prism on prism is back online" in caplog.text


async def test_command_echo_is_not_a_sign_of_life(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test commands published by the integration do not keep Prism online."""
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])
    await fire_burst(hass)

    freezer.tick(OFFLINE_TIMEOUT / 2)
    async_fire_mqtt_message(hass, "prism/1/command/set_mode", "3")
    freezer.tick(OFFLINE_TIMEOUT / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(POWER_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_unload_while_offline(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a config entry unloads cleanly once Prism is offline."""
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    freezer.tick(OFFLINE_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
