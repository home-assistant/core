"""Snapshot tests for Daikin Onecta climate entities."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta.models import GatewayDevice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FAKE_ACCESS_TOKEN

from tests.common import MockConfigEntry, snapshot_platform

FIXTURE_PATH = Path(__file__).parent / "fixtures"

SNAPSHOT_FIXTURES = (
    ("homehub", "homehub"),
    ("offlinedevice", "offlinedevice"),
    ("dry", "dry"),
    ("fanmode", "fanmode"),
    ("dry2", "dry2"),
    ("schedule", "schedule"),
    ("ururu", "ururu"),
    ("altherma", "altherma"),
    ("altherma3m", "altherma3m"),
    ("altherma_ratelimit", "altherma"),
    ("climate_fixedfanmode", "climate_fixedfanmode"),
    ("climate_homekit_fan_mode_aliases", "climate_fixedfanmode"),
    ("climate_floorheatingairflow", "climate_floorheatingairflow"),
    ("mc80z", "mc80z"),
    ("holidaymode", "holidaymode"),
    ("water_heater", "altherma_boost"),
    ("climate", "altherma"),
    ("minimal_data", "minimal_data"),
    ("gas", "gas"),
    ("button", "dry"),
    ("altherma_schedule", "altherma_schedule"),
    ("altherma_firmwareupdate", "altherma_firmwareupdate"),
    ("dx4_firmwareupdate", "dx4_firmwareavailable"),
    ("skyair", "skyair"),
)


@pytest.mark.parametrize(("scenario", "fixture"), SNAPSHOT_FIXTURES)
async def test_climate_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    scenario: str,
    fixture: str,
) -> None:
    """Snapshot climate entities for archived Daikin cloud responses."""
    fixture_data = json.loads((FIXTURE_PATH / f"{fixture}.json").read_text())
    gateway_devices = [GatewayDevice.from_dict(device) for device in fixture_data]

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

    climate_entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == CLIMATE_DOMAIN
    ]
    if not climate_entries:
        assert snapshot(name="climate_entities") == []
        return

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
