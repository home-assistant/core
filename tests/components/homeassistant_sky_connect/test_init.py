"""Test the Home Assistant SkyConnect integration."""

from unittest.mock import patch

from universal_silabs_flasher.const import ApplicationType

from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.components.homeassistant_sky_connect.util import FirmwareGuess
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_remove_invalid_entry(hass: HomeAssistant) -> None:
    """Test removing invalid entries."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "device": "/dev/serial/by-id/usb-ITEAD_SONOFF_Zigbee_3.0_USB_Dongle_Plus_V2_20230325081110-if00",
            "vid": "1A86",
            "pid": "55D4",
            "serial_number": "20230325081110",
            "manufacturer": "ITEAD",
            "description": "SONOFF Zigbee 3.0 USB Dongle Plus V2",
            "firmware": "cpc",
            "product": "SONOFF Zigbee 3.0 USB Dongle Plus V2",
        },
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    # The config entry was removed
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


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
