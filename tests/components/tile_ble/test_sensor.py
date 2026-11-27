"""Tests for the Tile BLE sensor."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_source,
    inject_bluetooth_service_info,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TILE_ADDRESS, TILE_SERVICE_INFO, setup_integration

ENTITY_ID = "sensor.tile_signal_strength"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the sensor platform."""
    with patch("homeassistant.components.tile_ble.PLATFORMS", [Platform.SENSOR]):
        yield


def _inject_advertisement(hass: HomeAssistant, rssi: int, source: str) -> None:
    """Inject an advertisement of the Tile with unchanged data."""
    inject_advertisement_with_source(
        hass,
        generate_ble_device(TILE_ADDRESS, TILE_SERVICE_INFO.name),
        generate_advertisement_data(
            local_name=TILE_SERVICE_INFO.name,
            service_data=TILE_SERVICE_INFO.service_data,
            service_uuids=TILE_SERVICE_INFO.service_uuids,
            rssi=rssi,
        ),
        source,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the signal strength sensor."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_signal_strength_updates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the sensor follows the RSSI when only the RSSI changes."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await setup_integration(hass, mock_config_entry)

    _inject_advertisement(hass, -80, TILE_SERVICE_INFO.source)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "-80"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_signal_strength_other_source(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an advertisement from a source that is not preferred is ignored."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await setup_integration(hass, mock_config_entry)

    _inject_advertisement(hass, -90, "proxy")
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "-60"
