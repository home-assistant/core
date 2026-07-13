"""Tests for the Bosch SHC sensor platform."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    light_switch_device,
    setup_integration,
    smart_plug_compact_device,
    smart_plug_device,
    thermostat_device,
    twinguard_device,
    wallthermostat_device,
)

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the sensor platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [
        pytest.param(
            {
                "thermostats": [thermostat_device()],
                "wallthermostats": [wallthermostat_device()],
                "twinguards": [twinguard_device()],
                "smart_plugs": [smart_plug_device()],
                "light_switches_bsm": [light_switch_device()],
                "smart_plugs_compact": [smart_plug_compact_device()],
            },
            id="entities",
        )
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot every sensor entity the platform can create, across all 6 buckets."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_session")
async def test_setup_no_devices_adds_nothing(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """No devices in any bucket means no sensor entities are created."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_all(SENSOR_DOMAIN) == []
