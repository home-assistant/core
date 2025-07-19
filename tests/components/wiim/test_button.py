"""pytest button.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wiim.consts import WiimHttpCommand
from wiim.exceptions import WiimException, WiimRequestException
from wiim.wiim_device import WiimDevice

from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.wiim.button import (
    BUTTON_DESCRIPTIONS,
    WiimButton,
    async_setup_entry,
)
from homeassistant.components.wiim.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.asyncio
async def test_button_setup_entry_http_available(
    mock_hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_wiim_device: WiimDevice,
    mock_add_entities: AsyncMock,
) -> None:
    """Test setting up button entities when HTTP API is available."""
    mock_config_entry.runtime_data = mock_wiim_device
    mock_wiim_device._http_api = AsyncMock()
    mock_wiim_device._available = True

    async_add_entities = AsyncMock()

    mock_http_api = MagicMock()
    mock_device = MagicMock()
    mock_device._http_api = mock_http_api
    mock_device.name = "WiiM Player"

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    async_add_entities.assert_called_once()
    added_entities = async_add_entities.call_args[0][0]

    assert all(isinstance(entity, WiimButton) for entity in added_entities)
    assert len(added_entities) > 0


@pytest.mark.asyncio
async def test_button_setup_entry_http_not_available(
    mock_hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_wiim_device: WiimDevice,
    mock_add_entities: AsyncMock,
) -> None:
    """Test setting up button entities when HTTP API is not available."""
    mock_config_entry.runtime_data = mock_wiim_device
    mock_wiim_device._http_api = None
    mock_wiim_device._available = True

    async_add_entities = AsyncMock()

    mock_device = MagicMock()
    mock_device._http_api = None
    mock_device.name = "WiiM Player"

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    async_add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_button_press_success(mock_wiim_device: WiimDevice) -> None:
    """Test pressing a button successfully."""
    mock_wiim_device._http_api = AsyncMock()

    reboot_description = next(
        d for d in BUTTON_DESCRIPTIONS if d.key == "reboot_device"
    )
    button = WiimButton(mock_wiim_device, reboot_description)
    button.entity_id = "button.test_reboot"

    with patch.object(
        mock_wiim_device, "_http_command_ok", new_callable=AsyncMock
    ) as mock_http_cmd_ok:
        await button.async_press()
        mock_http_cmd_ok.assert_awaited_once_with(WiimHttpCommand.REBOOT)


@pytest.mark.asyncio
async def test_button_press_http_api_missing_for_http_action(
    mock_wiim_device: WiimDevice,
) -> None:
    """Test pressing an HTTP API button when HTTP API is missing raises HomeAssistantError."""
    mock_wiim_device._http_api = None

    reboot_description = next(
        d for d in BUTTON_DESCRIPTIONS if d.key == "reboot_device"
    )
    button = WiimButton(mock_wiim_device, reboot_description)
    button.entity_id = "button.test_reboot"

    with pytest.raises(
        HomeAssistantError, match="HTTP API not available for action reboot_device"
    ):
        await button.async_press()


@pytest.mark.asyncio
async def test_button_press_sdk_exception(mock_wiim_device: WiimDevice) -> None:
    """Test pressing a button raises WiimRequestException."""
    mock_wiim_device._http_api = AsyncMock()

    reboot_description = next(
        d for d in BUTTON_DESCRIPTIONS if d.key == "reboot_device"
    )
    button = WiimButton(mock_wiim_device, reboot_description)
    button.entity_id = "button.test_reboot"

    with patch.object(
        mock_wiim_device, "_http_command_ok", new_callable=AsyncMock
    ) as mock_http_cmd_ok:
        mock_http_cmd_ok.side_effect = WiimRequestException("Mock HTTP error")
        with pytest.raises(
            WiimException, match="HTTP API not available for action reboot_device"
        ):
            await button.async_press()
        mock_http_cmd_ok.assert_awaited_once_with(WiimHttpCommand.REBOOT)


@pytest.mark.asyncio
async def test_button_attributes(mock_wiim_device: WiimDevice) -> None:
    """Test button entity attributes."""
    reboot_description = next(
        d for d in BUTTON_DESCRIPTIONS if d.key == "reboot_device"
    )
    button = WiimButton(mock_wiim_device, reboot_description)

    assert button.unique_id == f"{mock_wiim_device.udn}-{reboot_description.key}"
    assert button.device_class == ButtonDeviceClass.RESTART
    assert button.entity_description is reboot_description
    assert button.available == mock_wiim_device.available

    assert button.device_info is not None
    assert button.device_info["identifiers"] == {(DOMAIN, mock_wiim_device.udn)}
    assert button.device_info["name"] == mock_wiim_device.name
    assert button.device_info["manufacturer"] == mock_wiim_device._manufacturer
    assert button.device_info["model"] == mock_wiim_device.model_name
    assert button.device_info["sw_version"] == mock_wiim_device.firmware_version
