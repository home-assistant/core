"""Test init of Satel Integra integration."""

from copy import deepcopy
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import (
    MOCK_CONFIG_DATA,
    MOCK_CONFIG_OPTIONS,
    MOCK_OUTPUT_SUBENTRY,
    MOCK_PARTITION_SUBENTRY,
    MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
    MOCK_ZONE_SUBENTRY,
)

from tests.common import MockConfigEntry


async def test_config_flow_migration_version_1_2(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_satel: AsyncMock,
) -> None:
    """Test that the unique ID is migrated to the new format."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
        entry_id="SATEL_INTEGRA_CONFIG_ENTRY_1",
        version=1,
        minor_version=1,
    )
    config_entry.subentries = deepcopy(
        {
            MOCK_PARTITION_SUBENTRY.subentry_id: MOCK_PARTITION_SUBENTRY,
            MOCK_ZONE_SUBENTRY.subentry_id: MOCK_ZONE_SUBENTRY,
            MOCK_OUTPUT_SUBENTRY.subentry_id: MOCK_OUTPUT_SUBENTRY,
            MOCK_SWITCHABLE_OUTPUT_SUBENTRY.subentry_id: MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
        }
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 1
    assert config_entry.minor_version == 2

    assert config_entry == snapshot
