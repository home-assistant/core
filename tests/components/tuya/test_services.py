"""Test Tuya initialization."""

from __future__ import annotations

import pytest
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import DOMAIN
from homeassistant.components.tuya.services import SEND_TEXT_COMMAND
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import initialize_entry

from tests.common import MockConfigEntry


async def test_setup_services(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup of Tuya services."""

    await initialize_entry(hass, mock_manager, mock_config_entry, [])

    assert (services := hass.services.async_services_for_domain(DOMAIN))
    assert SEND_TEXT_COMMAND in services


@pytest.mark.parametrize(
    "mock_device_code",
    ["sjz_ftbc8rp8ipksdfpv"],
)
async def test_send_device_command(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Validate send_device_command."""

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "vpfdskpi8pr8cbtfzjs")}
    )
    assert device_entry is not None

    await hass.services.async_call(
        DOMAIN,
        SEND_TEXT_COMMAND,
        {
            "device_id": device_entry.id,
            "code": "up_down",
            "value": "up",
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        "vpfdskpi8pr8cbtfzjs", [{"code": "up_down", "value": "up"}]
    )
