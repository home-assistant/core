"""Tests for Vodafone Station image platform."""

from http import HTTPStatus
from io import BytesIO
from unittest.mock import AsyncMock, patch

from aiovodafone.const import WIFI_DATA
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.vodafone_station.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .const import TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2026-01-05T15:00:00+00:00")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""

    with patch("homeassistant.components.vodafone_station.PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2023-12-02T13:00:00+00:00")
async def test_image_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test image entity."""

    entity_id = f"image.vodafone_station_{TEST_SERIAL_NUMBER}_guest_network"

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # test image entities are generated as expected
    states = hass.states.async_all(IMAGE_DOMAIN)
    assert len(states) == 2

    state = states[0]
    assert state.name == f"Vodafone Station ({TEST_SERIAL_NUMBER}) Guest network"
    assert state.entity_id == entity_id

    access_token = state.attributes["access_token"]
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/{entity_id}?token={access_token}",
        "friendly_name": f"Vodafone Station ({TEST_SERIAL_NUMBER}) Guest network",
    }

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{TEST_SERIAL_NUMBER}-guest-qr-code"

    # test image download
    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{entity_id}")
    assert resp.status == HTTPStatus.OK

    body = await resp.read()
    assert body == snapshot

    assert (state := hass.states.async_all(IMAGE_DOMAIN)[0])
    assert state.state == "2023-12-02T13:00:00+00:00"


@pytest.mark.freeze_time("2023-12-02T13:00:00+00:00")
async def test_image_update(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test image update."""

    entity_id = f"image.vodafone_station_{TEST_SERIAL_NUMBER}_guest_network"

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{entity_id}")
    assert resp.status == HTTPStatus.OK

    resp_body = await resp.read()

    assert (state := hass.states.get(entity_id))
    assert state.state == "2023-12-02T13:00:00+00:00"

    mock_vodafone_station_router.get_wifi_data.return_value = {
        WIFI_DATA: {
            "guest": {
                "on": 1,
                "ssid": "Wifi-Guest",
                "qr_code": BytesIO(b"fake-qr-code-guest-updated"),
            },
            "guest_5g": {
                "on": 0,
                "ssid": "Wifi-Guest-5Ghz",
                "qr_code": BytesIO(b"fake-qr-code-guest-5ghz-updated"),
            },
        }
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    new_time = dt_util.utcnow()

    resp = await client.get(f"/api/image_proxy/{entity_id}")
    assert resp.status == HTTPStatus.OK

    resp_body_new = await resp.read()
    assert resp_body != resp_body_new

    assert (state := hass.states.get(entity_id))
    assert state.state == new_time.isoformat()


async def test_no_wifi_data(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test image entity."""

    mock_vodafone_station_router.get_wifi_data.return_value = {WIFI_DATA: {}}

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # test image entities are not generated
    states = hass.states.async_all(IMAGE_DOMAIN)
    assert len(states) == 0
