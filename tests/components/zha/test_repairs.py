"""Test ZHA repairs."""
from collections.abc import Callable
from unittest.mock import patch

import pytest
from universal_silabs_flasher.const import ApplicationType
from universal_silabs_flasher.flasher import Flasher

from homeassistant.components.homeassistant_sky_connect import (
    DOMAIN as SKYCONNECT_DOMAIN,
)
from homeassistant.components.zha.core.const import DOMAIN
from homeassistant.components.zha.repairs import (
    DISABLE_MULTIPAN_URL,
    ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED,
    HardwareType,
    detect_radio_hardware,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

SKYCONNECT_DEVICE = "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0"


def set_flasher_app_type(app_type: ApplicationType) -> Callable[[Flasher], None]:
    """Set the app type on the flasher."""

    def replacement(self: Flasher) -> None:
        self.app_type = app_type

    return replacement


def test_detect_radio_hardware(hass: HomeAssistant) -> None:
    """Test logic to detect radio hardware."""
    skyconnect_config_entry = MockConfigEntry(
        data={
            "device": SKYCONNECT_DEVICE,
            "vid": "10C4",
            "pid": "EA60",
            "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
            "manufacturer": "Nabu Casa",
            "description": "SkyConnect v1.0",
        },
        domain=SKYCONNECT_DOMAIN,
        options={},
        title="Home Assistant SkyConnect",
    )
    skyconnect_config_entry.add_to_hass(hass)

    assert detect_radio_hardware(hass, SKYCONNECT_DEVICE) == HardwareType.SKYCONNECT
    assert detect_radio_hardware(hass, SKYCONNECT_DEVICE + "_foo") == HardwareType.OTHER
    assert detect_radio_hardware(hass, "/dev/ttyAMA1") == HardwareType.OTHER

    with patch(
        "homeassistant.components.homeassistant_yellow.hardware.get_os_info",
        return_value={"board": "yellow"},
    ):
        assert detect_radio_hardware(hass, "/dev/ttyAMA1") == HardwareType.YELLOW
        assert detect_radio_hardware(hass, "/dev/ttyAMA2") == HardwareType.OTHER
        assert detect_radio_hardware(hass, SKYCONNECT_DEVICE) == HardwareType.SKYCONNECT


def test_detect_radio_hardware_failure(hass: HomeAssistant) -> None:
    """Test radio hardware detection failure."""

    with patch(
        "homeassistant.components.homeassistant_yellow.hardware.async_info",
        side_effect=HomeAssistantError(),
    ), patch(
        "homeassistant.components.homeassistant_sky_connect.hardware.async_info",
        side_effect=HomeAssistantError(),
    ):
        assert detect_radio_hardware(hass, SKYCONNECT_DEVICE) == HardwareType.OTHER


@pytest.mark.parametrize(
    ("detected_hardware", "expected_learn_more_url"),
    [
        (HardwareType.SKYCONNECT, DISABLE_MULTIPAN_URL[HardwareType.SKYCONNECT]),
        (HardwareType.YELLOW, DISABLE_MULTIPAN_URL[HardwareType.YELLOW]),
        (HardwareType.OTHER, None),
    ],
)
async def test_multipan_firmware_repair(
    hass: HomeAssistant,
    detected_hardware: HardwareType,
    expected_learn_more_url: str,
    config_entry: MockConfigEntry,
    mock_zigpy_connect,
) -> None:
    """Test creating a repair when multi-PAN firmware is installed and probed."""

    config_entry.add_to_hass(hass)

    # ZHA fails to set up
    with patch(
        "homeassistant.components.zha.repairs.Flasher.probe_app_type",
        side_effect=set_flasher_app_type(ApplicationType.CPC),
        autospec=True,
    ), patch(
        "homeassistant.components.zha.core.gateway.ZHAGateway.async_initialize",
        side_effect=RuntimeError(),
    ), patch(
        "homeassistant.components.zha.repairs.detect_radio_hardware",
        return_value=detected_hardware,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == ConfigEntryState.SETUP_ERROR

    await hass.config_entries.async_unload(config_entry.entry_id)

    issue_registry = ir.async_get(hass)

    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED,
    )

    # The issue is created when we fail to probe
    assert issue is not None
    assert issue.translation_placeholders["firmware_type"] == "CPC"
    assert issue.learn_more_url == expected_learn_more_url

    # If ZHA manages to start up normally after this, the issue will be deleted
    with mock_zigpy_connect:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED,
    )
    assert issue is None


async def test_multipan_firmware_no_repair_on_probe_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a repair is not created when multi-PAN firmware cannot be probed."""

    config_entry.add_to_hass(hass)

    # ZHA fails to set up
    with patch(
        "homeassistant.components.zha.repairs.Flasher.probe_app_type",
        side_effect=set_flasher_app_type(None),
        autospec=True,
    ), patch(
        "homeassistant.components.zha.core.gateway.ZHAGateway.async_initialize",
        side_effect=RuntimeError(),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == ConfigEntryState.SETUP_ERROR

    await hass.config_entries.async_unload(config_entry.entry_id)

    # No repair is created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED,
    )
    assert issue is None


async def test_multipan_firmware_retry_on_probe_ezsp(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_zigpy_connect,
) -> None:
    """Test that ZHA is reloaded when EZSP firmware is probed."""

    config_entry.add_to_hass(hass)

    # ZHA fails to set up
    with patch(
        "homeassistant.components.zha.repairs.Flasher.probe_app_type",
        side_effect=set_flasher_app_type(ApplicationType.EZSP),
        autospec=True,
    ), patch(
        "homeassistant.components.zha.core.gateway.ZHAGateway.async_initialize",
        side_effect=RuntimeError(),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # The config entry state is `SETUP_RETRY`, not `SETUP_ERROR`!
        assert config_entry.state == ConfigEntryState.SETUP_RETRY

    await hass.config_entries.async_unload(config_entry.entry_id)

    # No repair is created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED,
    )
    assert issue is None
