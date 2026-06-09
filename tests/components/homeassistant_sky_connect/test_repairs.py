"""Test the Home Assistant SkyConnect repairs flow."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.hassio import (
    DOMAIN as HASSIO_DOMAIN,
    AddonInfo,
    AddonState,
)
from homeassistant.components.homeassistant_hardware.repair_helpers import (
    ISSUE_MULTI_PAN_MIGRATION,
)
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    CONF_DISABLE_MULTI_PAN,
    get_multiprotocol_addon_manager,
)
from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator

DEVICE = (
    "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0"
    "_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
)


@pytest.mark.usefixtures("supervisor_client")
async def test_multi_pan_migration_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the multi-PAN migration repair flow reverts the firmware with progress."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})
    assert await async_setup_component(hass, "repairs", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "description": "SkyConnect v1.0",
            "device": DEVICE,
            "vid": "10C4",
            "pid": "EA60",
            "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
            "manufacturer": "Nabu Casa",
            "product": "SkyConnect v1.0",
            "firmware": "cpc",
            "firmware_version": None,
        },
        title="Home Assistant SkyConnect",
        version=1,
        minor_version=4,
    )
    config_entry.add_to_hass(hass)

    # Multi-PAN addon is running and using the radio
    mock_multipan_manager = Mock(spec_set=await get_multiprotocol_addon_manager(hass))
    mock_multipan_manager.addon_name = "Silicon Labs Multiprotocol"
    mock_multipan_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={"device": DEVICE},
        state=AddonState.RUNNING,
        update_available=False,
        version="1.0.0",
    )

    mock_fw_manifest = Mock()
    mock_fw_manifest.filename = "skyconnect_zigbee_ncp_7.4.4.0.gbl"
    mock_fw_client = AsyncMock()
    mock_fw_client.async_update_data.return_value = Mock(firmwares=[mock_fw_manifest])
    mock_fw_client.async_fetch_firmware.return_value = b"fake_firmware"

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.os.path.exists",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.get_multiprotocol_addon_manager",
            return_value=mock_multipan_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.async_flash_silabs_firmware",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.async_firmware_flashing_context"
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.FirmwareUpdateClient",
            return_value=mock_fw_client,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
            return_value=True,
        ),
    ):
        # Setting up the entry creates the migration issue
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await async_process_repairs_platforms(hass)
        client = await hass_client()

        issue_id = f"{ISSUE_MULTI_PAN_MIGRATION}_{config_entry.entry_id}"
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

        # The repair flow jumps straight into the uninstall confirmation form
        result = await start_repair_fix_flow(client, DOMAIN, issue_id)
        flow_id = result["flow_id"]
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "uninstall_addon"

        # Confirm the migration: uninstall the multiprotocol addon (progress)
        result = await process_repair_fix_flow(
            client, flow_id, json={CONF_DISABLE_MULTI_PAN: True}
        )
        assert result["type"] == FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "uninstall_multiprotocol_addon"
        assert result["progress_action"] == "uninstall_multiprotocol_addon"
        await hass.async_block_till_done(wait_background_tasks=True)

        # Flash the Zigbee firmware (progress)
        result = await process_repair_fix_flow(client, flow_id)
        assert result["type"] == FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "install_zigbee_firmware"
        assert result["progress_action"] == "install_zigbee_firmware"
        await hass.async_block_till_done(wait_background_tasks=True)

        # Flashing complete, the flow finishes
        result = await process_repair_fix_flow(client, flow_id)
        assert result["type"] == FlowResultType.CREATE_ENTRY

    # The firmware was reverted back to Zigbee
    assert config_entry.data["firmware"] == "ezsp"
