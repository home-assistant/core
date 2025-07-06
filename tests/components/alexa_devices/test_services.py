"""Tests for Alexa Devices services."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.const import (
    ATTR_SOUND,
    ATTR_SOUND_VARIANT,
    ATTR_TEXT_COMMAND,
    DOMAIN,
)
from homeassistant.components.alexa_devices.services import (
    SERVICE_SOUND_NOTIFICATION,
    SERVICE_TEXT_COMMAND,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry


async def test_setup_services(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup of Alexa Devices services."""
    await setup_integration(hass, mock_config_entry)

    assert (services := hass.services.async_services_for_domain(DOMAIN))
    assert SERVICE_TEXT_COMMAND in services
    assert SERVICE_SOUND_NOTIFICATION in services


async def test_send_sound_service(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test send sound service."""

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_SERIAL_NUMBER)}
    )
    assert device_entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SOUND_NOTIFICATION,
        {
            ATTR_SOUND: "chimes_bells",
            ATTR_SOUND_VARIANT: 1,
            ATTR_DEVICE_ID: device_entry.id,
        },
        blocking=True,
    )

    assert mock_amazon_devices_client.call_alexa_sound.call_count == 1
    assert mock_amazon_devices_client.call_alexa_sound.call_args == snapshot


async def test_send_text_service(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test send text service."""

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_SERIAL_NUMBER)}
    )
    assert device_entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TEXT_COMMAND,
        {
            ATTR_TEXT_COMMAND: "Play B.B.C. radio on TuneIn",
            ATTR_DEVICE_ID: device_entry.id,
        },
        blocking=True,
    )

    assert mock_amazon_devices_client.call_alexa_text_command.call_count == 1
    assert mock_amazon_devices_client.call_alexa_text_command.call_args == snapshot
