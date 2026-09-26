"""Tests for the WeatherFlow event platform."""

from unittest.mock import patch

import pytest
from pyweatherflowudp.aioudp import LocalEndpoint
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.weatherflow.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ALL_DEVICE_PACKETS = (
    "hub_status.json",
    "device.json",
    "obs_st.json",
    "air_status.json",
    "obs_air.json",
    "sky_status.json",
    "obs_sky.json",
)


async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
) -> None:
    """Test each device only gets event entities for the events it sends."""
    with patch("homeassistant.components.weatherflow.PLATFORMS", [Platform.EVENT]):
        await setup_integration(
            hass, mock_config_entry, mock_udp_endpoint, ALL_DEVICE_PACKETS
        )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "unique_id",
    [
        "HB-00000001_precip_start_event",
        "HB-00000001_lightning_strike_event",
        "AR-00000001_precip_start_event",
        "SK-00000001_lightning_strike_event",
    ],
)
async def test_unsupported_event_entity_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
    unique_id: str,
) -> None:
    """Test an event entity for an event the device never sends is removed."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        EVENT_DOMAIN, DOMAIN, unique_id, config_entry=mock_config_entry
    )

    await setup_integration(
        hass, mock_config_entry, mock_udp_endpoint, ALL_DEVICE_PACKETS
    )

    assert entity_registry.async_get_entity_id(EVENT_DOMAIN, DOMAIN, unique_id) is None
