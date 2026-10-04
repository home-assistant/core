"""Snapshot tests for Daikin Onecta climate entities."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta.models import GatewayDevice
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.single_file import SingleFileAmberSnapshotExtension
from syrupy.location import PyTestLocation

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FAKE_ACCESS_TOKEN

from tests.common import MockConfigEntry
from tests.syrupy import HomeAssistantSnapshotExtension

FIXTURE_PATH = Path(__file__).parent / "fixtures"

FIXTURES = (
    "altherma",
    "altherma3m",
    "altherma_boost",
    "altherma_firmwareupdate",
    "altherma_schedule",
    "climate_fixedfanmode",
    "climate_floorheatingairflow",
    "dry",
    "dry2",
    "dx4_firmwareavailable",
    "fanmode",
    "gas",
    "holidaymode",
    "homehub",
    "mc80z",
    "minimal_data",
    "nomodel_id",
    "offlinedevice",
    "schedule",
    "skyair",
    "ururu",
)


class SingleFileHomeAssistantSnapshotExtension(
    HomeAssistantSnapshotExtension, SingleFileAmberSnapshotExtension
):
    """Store Home Assistant snapshots in separate files."""

    @classmethod
    def dirname(cls, *, test_location: PyTestLocation) -> str:
        """Return the per-test snapshot directory."""
        return str(
            Path(test_location.filepath).parent / "snapshots" / test_location.basename
        )


@pytest.mark.parametrize("fixture", FIXTURES)
async def test_climate_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fixture: str,
) -> None:
    """Snapshot climate entities for archived Daikin cloud responses."""
    fixture_data = json.loads((FIXTURE_PATH / f"{fixture}.json").read_text())
    response_data = (
        fixture_data
        if isinstance(fixture_data, list)
        else fixture_data["data"]["json_data"]
    )
    gateway_devices = [GatewayDevice.from_dict(device) for device in response_data]

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            new=AsyncMock(return_value=FAKE_ACCESS_TOKEN),
        ),
        patch(
            "homeassistant.components.daikin_onecta.daikin_api."
            "OnectaClient.get_gateway_devices",
            new=AsyncMock(return_value=gateway_devices),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    climate_entities = {}
    for entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if entry.domain != CLIMATE_DOMAIN:
            continue
        state = hass.states.get(entry.entity_id)
        assert state is not None
        climate_entities[entry.entity_id] = {"entry": entry, "state": state}

    assert climate_entities == snapshot(
        name=fixture, extension_class=SingleFileHomeAssistantSnapshotExtension
    )
