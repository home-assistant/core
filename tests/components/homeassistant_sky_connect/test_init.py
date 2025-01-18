"""Test the Home Assistant SkyConnect integration."""

from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareGuess,
)
from homeassistant.components.homeassistant_sky_connect.const import (
    DOMAIN,
    HardwareVariant,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_entry_migration_v2(hass: HomeAssistant) -> None:
    """Test migrating config entries from v1 to v2 format."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "device": "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
            "vid": "10C4",
            "pid": "EA60",
            "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
            "manufacturer": "Nabu Casa",
            "description": "SkyConnect v1.0",
        },
        version=1,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_sky_connect.guess_firmware_type",
        return_value=FirmwareGuess(
            is_running=True,
            firmware_type=ApplicationType.SPINEL,
            source="otbr",
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 1
    assert config_entry.minor_version == 2
    assert config_entry.data == {
        "description": "SkyConnect v1.0",
        "device": "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
        "vid": "10C4",
        "pid": "EA60",
        "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
        "manufacturer": "Nabu Casa",
        "product": "SkyConnect v1.0",  # `description` has been copied to `product`
        "firmware": "spinel",  # new key
    }

    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    ("hw_variant", "title", "expected_title", "fw_type"),
    [
        (
            HardwareVariant.SKYCONNECT,
            "Home Assistant SkyConnect",
            "Home Assistant SkyConnect (Zigbee)",
            ApplicationType.EZSP.value,
        ),
        (
            HardwareVariant.SKYCONNECT,
            "Home Assistant SkyConnect (Something)",
            "Home Assistant SkyConnect (Zigbee)",
            ApplicationType.EZSP.value,
        ),
        (
            HardwareVariant.CONNECT_ZBT1,
            "Some Random Name",
            "Home Assistant Connect ZBT-1 (Thread)",
            ApplicationType.SPINEL.value,
        ),
        (
            HardwareVariant.CONNECT_ZBT1,
            "Home Assistant Connect ZBT-1 (Thread)",
            "Home Assistant Connect ZBT-1 (Thread)",
            ApplicationType.SPINEL.value,
        ),
        (
            HardwareVariant.CONNECT_ZBT1,
            "Home Assistant Connect ZBT-1 (Thread)",
            "Home Assistant Connect ZBT-1",
            ApplicationType.GECKO_BOOTLOADER,
        ),
    ],
)
async def test_config_entry_gets_renamed(
    hass: HomeAssistant,
    hw_variant: HardwareVariant,
    title: str,
    expected_title: str,
    fw_type: str,
) -> None:
    """Test that the correct firmware type suffix is added to the config entry title."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={
            "device": "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
            "vid": "10C4",
            "pid": "EA60",
            "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
            "manufacturer": "Nabu Casa",
            "product": hw_variant.usb_product_name,
            "firmware": fw_type,
        },
        minor_version=2,
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.title == expected_title
    await hass.config_entries.async_unload(config_entry.entry_id)
