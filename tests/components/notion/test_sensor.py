"""Test Notion sensors."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.notion.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import JsonObjectType


@pytest.fixture(name="data_listener")
def data_listener_fixture() -> JsonObjectType:
    """Define listener data with a temperature listener."""
    return load_json_object_fixture("listener_data_temperature.json", DOMAIN)


@pytest.mark.usefixtures("mock_aionotion")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test the sensors."""
    with patch("homeassistant.components.notion.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
