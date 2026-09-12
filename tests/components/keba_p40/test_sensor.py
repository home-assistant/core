"""Tests for KEBA P40 sensors."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

from keba_kecontact_p40 import Wallbox
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.keba_p40.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_load_fixture, snapshot_platform


@pytest.mark.usefixtures("mock_client", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the KEBA P40 sensors via snapshot."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_line_sensors_none_without_lines(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test line current/voltage sensors return None when meter has no lines."""
    data: dict[str, Any] = json.loads(
        await async_load_fixture(hass, "wallbox.json", DOMAIN)
    )
    data["meter"]["lines"] = []
    wallbox_no_lines = Wallbox.from_api(data)
    mock_client.get_wallbox.return_value = wallbox_no_lines
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.garage_voltage_l1").state == "unknown"
    assert hass.states.get("sensor.garage_current_l1").state == "unknown"
