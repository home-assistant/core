"""Test Yellow firmware update entity."""

from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant_hardware.helpers import (
    async_notify_firmware_info,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.components.homeassistant_yellow.const import RADIO_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

UPDATE_ENTITY_ID = "update.home_assistant_yellow_radio_firmware"


async def test_yellow_update_entity(hass: HomeAssistant) -> None:
    """Test the Yellow firmware update entity."""
    await async_setup_component(hass, "homeassistant", {})

    # Set up the Yellow integration
    yellow_config_entry = MockConfigEntry(
        title="Home Assistant Yellow",
        domain="homeassistant_yellow",
        data={
            "firmware": "ezsp",
            "firmware_version": "7.3.1.0 build 0",
            "device": RADIO_DEVICE,
        },
        version=1,
        minor_version=3,
    )
    yellow_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homeassistant_yellow.is_hassio", return_value=True
        ),
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ),
    ):
        assert await hass.config_entries.async_setup(yellow_config_entry.entry_id)
        await hass.async_block_till_done()

    # Pretend ZHA loaded and notified hardware of the running firmware
    await async_notify_firmware_info(
        hass,
        "zha",
        FirmwareInfo(
            device=RADIO_DEVICE,
            firmware_type=ApplicationType.EZSP,
            firmware_version="7.3.1.0 build 0",
            owners=[],
            source="zha",
        ),
    )
    await hass.async_block_till_done()

    state_ezsp = hass.states.get(UPDATE_ENTITY_ID)
    assert state_ezsp is not None
    assert state_ezsp.state == "unknown"
    assert state_ezsp.attributes["title"] == "EmberZNet Zigbee"
    assert state_ezsp.attributes["installed_version"] == "7.3.1.0"
    assert state_ezsp.attributes["latest_version"] is None

    # Now, have OTBR push some info
    await async_notify_firmware_info(
        hass,
        "otbr",
        FirmwareInfo(
            device=RADIO_DEVICE,
            firmware_type=ApplicationType.SPINEL,
            firmware_version="SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4; EFR32; Oct 21 2024 14:40:57",
            owners=[],
            source="otbr",
        ),
    )
    await hass.async_block_till_done()

    # After the firmware update, the entity has the new version and the correct state
    state_spinel = hass.states.get(UPDATE_ENTITY_ID)
    assert state_spinel is not None
    assert state_spinel.state == "unknown"
    assert state_spinel.attributes["title"] == "OpenThread RCP"
    assert state_spinel.attributes["installed_version"] == "2.4.4.0"
    assert state_spinel.attributes["latest_version"] is None


@pytest.mark.parametrize(
    ("firmware", "version", "expected"),
    [
        ("ezsp", "7.3.1.0 build 0", "EmberZNet Zigbee 7.3.1.0"),
        ("spinel", "SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4", "OpenThread RCP 2.4.4.0"),
        ("bootloader", "2.4.2", "Gecko Bootloader 2.4.2"),
        ("cpc", "4.3.2", "Multiprotocol 4.3.2"),
        ("router", "1.2.3.4", "Unknown 1.2.3.4"),  # Not supported but still shown
    ],
)
async def test_yellow_update_entity_state(
    hass: HomeAssistant, firmware: str, version: str, expected: str
) -> None:
    """Test the Yellow firmware update entity with different firmware types."""
    await async_setup_component(hass, "homeassistant", {})

    # Set up the Yellow integration
    yellow_config_entry = MockConfigEntry(
        title="Home Assistant Yellow",
        domain="homeassistant_yellow",
        data={
            "firmware": firmware,
            "firmware_version": version,
            "device": RADIO_DEVICE,
        },
        version=1,
        minor_version=3,
    )
    yellow_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homeassistant_yellow.is_hassio", return_value=True
        ),
        patch(
            "homeassistant.components.homeassistant_yellow.get_os_info",
            return_value={"board": "yellow"},
        ),
    ):
        assert await hass.config_entries.async_setup(yellow_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY_ID)
    assert state is not None
    assert (
        f"{state.attributes['title']} {state.attributes['installed_version']}"
        == expected
    )
