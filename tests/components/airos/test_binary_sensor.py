"""Test the Ubiquiti airOS binary sensors."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("ap_fixture"),
    [
        "airos_loco5ac_ap-ptp.json",  # v8 ptp
        "airos_liteapgps_ap_ptmp_40mhz.json",  # v8 ptmp
        "airos_NanoStation_loco_M5_v6.3.16_XM_sta.json",  # v6 XM (different login process)
        "airos_NanoStation_M5_sta_v6.3.16.json",  # v6 XW
    ],
    indirect=True,
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_airos_client: AsyncMock,
    mock_async_get_firmware_data: AsyncMock,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
