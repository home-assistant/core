"""Tests for satel integra diagnostics."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.satel_integra import (
    CONF_ARM_HOME_MODE,
    CONF_OUTPUT_NUMBER,
    CONF_PARTITION_NUMBER,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_ZONE,
)
from homeassistant.components.satel_integra.const import (
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_satel: AsyncMock,
) -> None:
    """Test diagnostics for config entry."""
    config_entry.add_to_hass(hass)
    config_entry.subentries = {
        "ID_PARTITION": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_PARTITION,
            subentry_id="ID_PARTITION",
            unique_id="partition_1",
            title="Home",
            data={
                CONF_NAME: "Home",
                CONF_ARM_HOME_MODE: 1,
                CONF_PARTITION_NUMBER: 1,
            },
        ),
        "ID_ZONE": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_ZONE,
            subentry_id="ID_ZONE",
            unique_id="zone_1",
            title="Zone 1",
            data={
                CONF_NAME: "Zone 1",
                CONF_ZONE_TYPE: BinarySensorDeviceClass.MOTION,
                CONF_ZONE_NUMBER: 1,
            },
        ),
        "ID_OUTPUT": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_OUTPUT,
            subentry_id="ID_OUTPUT",
            unique_id="output_1",
            title="Output 1",
            data={
                CONF_NAME: "Output 1",
                CONF_ZONE_TYPE: BinarySensorDeviceClass.SAFETY,
                CONF_OUTPUT_NUMBER: 1,
            },
        ),
        "ID_SWITCHABLE_OUTPUT": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
            subentry_id="ID_SWITCHABLE_OUTPUT",
            unique_id="switchable_output_1",
            title="Switchable Output 1",
            data={
                CONF_NAME: "Switchable Output 1",
                CONF_SWITCHABLE_OUTPUT_NUMBER: 1,
            },
        ),
    }

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics == snapshot(exclude=props("created_at", "modified_at", "id"))
