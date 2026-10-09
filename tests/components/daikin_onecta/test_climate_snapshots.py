"""Snapshot tests for Daikin Onecta climate entities."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta.models import GatewayDevice
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.single_file import SingleFileAmberSnapshotExtension
from syrupy.location import PyTestLocation

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FAKE_ACCESS_TOKEN

from tests.common import MockConfigEntry
from tests.syrupy import HomeAssistantSnapshotExtension

FIXTURE_PATH = Path(__file__).parent / "fixtures"
CLIMATE_ENTITY_ID = "climate.werkkamer_room_temperature"

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


def _load_gateway_devices(fixture: str) -> list[GatewayDevice]:
    """Load gateway devices from an archived cloud response."""
    fixture_data = json.loads((FIXTURE_PATH / f"{fixture}.json").read_text())
    response_data = (
        fixture_data
        if isinstance(fixture_data, list)
        else fixture_data["data"]["json_data"]
    )
    return [GatewayDevice.from_dict(device) for device in response_data]


async def _async_setup_fixture(
    hass: HomeAssistant, config_entry: MockConfigEntry, fixture: str
) -> None:
    """Set up the integration using an archived cloud response."""
    gateway_devices = _load_gateway_devices(fixture)

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


@pytest.mark.parametrize("fixture", FIXTURES)
async def test_climate_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fixture: str,
) -> None:
    """Snapshot climate entities for archived Daikin cloud responses."""
    await _async_setup_fixture(hass, config_entry, fixture)

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


@pytest.mark.parametrize("fixture", FIXTURES)
async def test_all_platform_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fixture: str,
) -> None:
    """Snapshot all entities from each archived Daikin cloud response."""
    await _async_setup_fixture(hass, config_entry, fixture)

    entities = {}
    for entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        state = hass.states.get(entry.entity_id)
        assert state is not None
        entities[entry.entity_id] = {"entry": entry, "state": state}

    assert entities == snapshot(
        name=fixture, extension_class=SingleFileHomeAssistantSnapshotExtension
    )


async def test_fan_mode_changes_with_hvac_mode(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Update the fan state from each native HVAC operation mode."""
    await _async_setup_fixture(hass, config_entry, "fanmode")
    api = config_entry.runtime_data.api
    api.client.patch_characteristic = AsyncMock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {"entity_id": "climate.sala_room_temperature", "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    state = hass.states.get("climate.sala_room_temperature")
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_FAN_MODE] == "3"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {"entity_id": "climate.sala_room_temperature", "hvac_mode": HVACMode.DRY},
        blocking=True,
    )
    state = hass.states.get("climate.sala_room_temperature")
    assert state is not None
    assert state.state == HVACMode.DRY
    assert state.attributes[ATTR_FAN_MODE] == "auto"
