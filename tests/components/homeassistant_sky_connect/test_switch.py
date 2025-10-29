"""Test SkyConnect beta firmware switch entity."""

from unittest.mock import Mock, call, patch

from ha_silabs_firmware_client import FirmwareManifest, FirmwareMetadata
import pytest
from yarl import URL

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import USB_DATA_ZBT1

from tests.common import MockConfigEntry, mock_restore_cache

SWITCH_ENTITY_ID = "switch.home_assistant_connect_zbt_1_9e2adbd7_beta_firmware_updates"

TEST_MANIFEST = FirmwareManifest(
    url=URL("https://example.org/firmware"),
    html_url=URL("https://example.org/release_notes"),
    created_at=dt_util.utcnow(),
    firmwares=(
        FirmwareMetadata(
            filename="skyconnect_zigbee_ncp_test.gbl",
            checksum="aaa",
            size=123,
            release_notes="Some release notes go here",
            metadata={
                "baudrate": 115200,
                "ezsp_version": "7.4.4.0",
                "fw_type": "zigbee_ncp",
                "fw_variant": None,
                "metadata_version": 2,
                "sdk_version": "4.4.4",
            },
            url=URL("https://example.org/firmwares/skyconnect_zigbee_ncp_test.gbl"),
        ),
    ),
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("service", "target_state", "expected_prerelease"),
    [
        (SERVICE_TURN_ON, STATE_ON, True),
        (SERVICE_TURN_OFF, STATE_OFF, False),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    service: str,
    target_state: str,
    expected_prerelease: bool,
) -> None:
    """Test turning switch on/off updates state and coordinator."""
    await async_setup_component(hass, "homeassistant", {})

    # Start with opposite state
    mock_restore_cache(
        hass,
        [
            State(
                SWITCH_ENTITY_ID,
                STATE_ON if service == SERVICE_TURN_OFF else STATE_OFF,
            )
        ],
    )

    # Set up the ZBT-1 integration
    zbt1_config_entry = MockConfigEntry(
        title="Home Assistant Connect ZBT-1",
        domain="homeassistant_sky_connect",
        data={
            "firmware": "ezsp",
            "firmware_version": "7.3.1.0 build 0",
            "device": USB_DATA_ZBT1.device,
            "manufacturer": USB_DATA_ZBT1.manufacturer,
            "pid": USB_DATA_ZBT1.pid,
            "product": USB_DATA_ZBT1.description,
            "serial_number": USB_DATA_ZBT1.serial_number,
            "vid": USB_DATA_ZBT1.vid,
        },
        version=1,
        minor_version=3,
    )
    zbt1_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.coordinator.FirmwareUpdateClient"
        ) as mock_client,
        patch(
            "homeassistant.components.homeassistant_hardware.coordinator.FirmwareUpdateCoordinator.async_refresh"
        ) as mock_refresh,
    ):
        mock_client.return_value.async_update_data.return_value = TEST_MANIFEST
        mock_client.return_value.update_prerelease = Mock()

        assert await hass.config_entries.async_setup(zbt1_config_entry.entry_id)
        await hass.async_block_till_done()

        # Reset mocks after setup
        mock_client.return_value.update_prerelease.reset_mock()
        mock_refresh.reset_mock()

        # Call the service
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )

        # Verify state changed
        state = hass.states.get(SWITCH_ENTITY_ID)
        assert state is not None
        assert state.state == target_state

        # Verify coordinator methods were called
        assert mock_client.return_value.update_prerelease.mock_calls == [
            call(expected_prerelease)
        ]
        assert len(mock_refresh.mock_calls) == 1
