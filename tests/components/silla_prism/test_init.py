"""Test the Silla Prism setup."""

from unittest.mock import patch

from homeassistant.components.silla_prism.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import fire_burst, setup_integration
from .const import BASE_TOPIC, HELLO_PAYLOAD, HELLO_TOPIC, SERIAL

from tests.common import MockConfigEntry, async_fire_mqtt_message
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

    device = device_registry.async_get_device(identifiers={(DOMAIN, BASE_TOPIC)})
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

    device = device_registry.async_get_device(identifiers={(DOMAIN, BASE_TOPIC)})
    assert device is not None
    assert device.serial_number == SERIAL
    assert device.sw_version == "3.2.77"
