"""Tests for the devolo Home Network images."""

from http import HTTPStatus
from unittest.mock import AsyncMock

from devolo_plc_api.exceptions.device import DeviceUnavailable
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.devolo_home_network.const import SHORT_UPDATE_INTERVAL
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import configure_integration
from .const import GUEST_WIFI_CHANGED
from .mock import MockDevice

from tests.common import async_fire_time_changed
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_device")
async def test_image_setup(hass: HomeAssistant) -> None:
    """Test default setup of the image component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get(
            f"{IMAGE_DOMAIN}.{device_name}_guest_wi_fi_credentials_as_qr_code"
        )
        is not None
    )

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.freeze_time("2023-01-13 12:00:00+00:00")
async def test_guest_wifi_qr(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test showing a QR code of the guest wifi credentials."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{IMAGE_DOMAIN}.{device_name}_guest_wi_fi_credentials_as_qr_code"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state.name == "Mock Title Guest Wi-Fi credentials as QR code"
    assert state.state == dt_util.utcnow().isoformat()
    assert entity_registry.async_get(state_key) == snapshot

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{state_key}")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == snapshot

    # Emulate device failure
    mock_device.device.async_get_wifi_guest_access.side_effect = DeviceUnavailable()
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    mock_device.device.async_get_wifi_guest_access = AsyncMock(
        return_value=GUEST_WIFI_CHANGED
    )
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == dt_util.utcnow().isoformat()

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{state_key}")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() != body

    await hass.config_entries.async_unload(entry.entry_id)
