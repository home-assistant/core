"""Snapshot tests for each Daikin Onecta entity platform."""

from datetime import UTC, datetime
from itertools import product
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.daikin_onecta import PLATFORMS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .platform_helpers import _async_setup_fixture

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

EMPTY_PLATFORMS = {
    "altherma": {Platform.FAN, Platform.UPDATE},
    "altherma3m": {Platform.FAN, Platform.SWITCH},
    "altherma_boost": {Platform.FAN, Platform.SWITCH},
    "altherma_firmwareupdate": {
        Platform.CLIMATE,
        Platform.FAN,
        Platform.SELECT,
        Platform.SWITCH,
    },
    "altherma_schedule": {Platform.FAN, Platform.SWITCH},
    "climate_fixedfanmode": {
        Platform.FAN,
        Platform.SWITCH,
        Platform.WATER_HEATER,
    },
    "climate_floorheatingairflow": {
        Platform.FAN,
        Platform.UPDATE,
        Platform.WATER_HEATER,
    },
    "dry": {Platform.FAN, Platform.SWITCH, Platform.WATER_HEATER},
    "dry2": {Platform.FAN, Platform.SWITCH, Platform.WATER_HEATER},
    "dx4_firmwareavailable": {
        Platform.FAN,
        Platform.SWITCH,
        Platform.WATER_HEATER,
    },
    "fanmode": {Platform.FAN, Platform.SWITCH, Platform.WATER_HEATER},
    "gas": {Platform.FAN, Platform.SWITCH},
    "holidaymode": {Platform.CLIMATE, Platform.FAN, Platform.SWITCH},
    "homehub": {
        Platform.BINARY_SENSOR,
        Platform.CLIMATE,
        Platform.FAN,
        Platform.SELECT,
        Platform.SWITCH,
        Platform.UPDATE,
        Platform.WATER_HEATER,
    },
    "mc80z": {Platform.SWITCH},
    "minimal_data": {
        Platform.FAN,
        Platform.SELECT,
        Platform.SWITCH,
        Platform.UPDATE,
    },
    "nomodel_id": {Platform.FAN, Platform.SWITCH},
    "offlinedevice": {
        Platform.CLIMATE,
        Platform.FAN,
        Platform.SWITCH,
        Platform.WATER_HEATER,
    },
    "skyair": {Platform.FAN, Platform.SWITCH, Platform.WATER_HEATER},
    "schedule": {Platform.FAN, Platform.SWITCH, Platform.WATER_HEATER},
    "ururu": {Platform.FAN, Platform.SWITCH, Platform.WATER_HEATER},
}

SNAPSHOT_CASES = tuple(
    pytest.param(fixture, platform, id=f"{fixture}-{platform}")
    for fixture, platform in product(FIXTURES, PLATFORMS)
    if platform not in EMPTY_PLATFORMS.get(fixture, set())
)


@pytest.mark.parametrize(("fixture", "platform"), SNAPSHOT_CASES)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_platform_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    fixture: str,
    platform: Platform,
) -> None:
    """Snapshot each entity platform for every response fixture."""
    freezer.move_to(datetime(2026, 10, 15, 12, tzinfo=UTC))
    with patch("homeassistant.components.daikin_onecta.PLATFORMS", [platform]):
        await _async_setup_fixture(hass, config_entry, fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
