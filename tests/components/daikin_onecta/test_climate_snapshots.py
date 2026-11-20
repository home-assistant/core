"""Snapshot tests for Daikin Onecta climate entities."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.single_file import SingleFileAmberSnapshotExtension
from syrupy.location import PyTestLocation

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    ClimateEntityStateAttribute,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .platform_helpers import _async_setup_fixture

CLIMATE_ENTITY_ID = "climate.test_office_room_temperature"

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
    "skyair",
    "schedule",
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
async def test_all_platform_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    fixture: str,
) -> None:
    """Snapshot all entities from each archived Daikin cloud response."""
    freezer.move_to(datetime(2026, 10, 15, 12, tzinfo=UTC))
    await _async_setup_fixture(hass, config_entry, fixture)

    entities = {}
    for entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        state = hass.states.get(entry.entity_id)
        assert (state is None) == (entry.disabled_by is not None)
        entities[entry.entity_id] = {"entry": entry, "state": state}

    assert entities == snapshot(
        name=fixture, extension_class=SingleFileHomeAssistantSnapshotExtension
    )


async def test_fan_mode_changes_with_hvac_mode(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Update the fan state from each native HVAC operation mode."""
    await _async_setup_fixture(hass, config_entry, "fanmode")
    api = config_entry.runtime_data
    api.client.patch_characteristic = AsyncMock()
    entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            "entity_id": entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ClimateEntityStateAttribute.FAN_MODE] == "3"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            "entity_id": entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.DRY,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.DRY
    assert state.attributes[ClimateEntityStateAttribute.FAN_MODE] == "auto"
