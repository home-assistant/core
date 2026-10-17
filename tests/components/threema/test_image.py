"""Test the Threema Gateway image platform."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from aiothreema import derive_public_key
import segno

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_GATEWAY_ID, MOCK_PRIVATE_KEY

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

ENTITY_ID = "image.threema_testgwy_gateway_qr_code"


async def test_qr_code_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry_with_keys: MockConfigEntry,
    mock_credentials: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the QR code encodes the gateway ID and its public key."""
    mock_config_entry_with_keys.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.image.segno.make",
        wraps=segno.make,
    ) as mock_make:
        await hass.config_entries.async_setup(mock_config_entry_with_keys.entry_id)
        await hass.async_block_till_done()

    mock_make.assert_called_once_with(
        f"3mid:{MOCK_GATEWAY_ID},{derive_public_key(MOCK_PRIVATE_KEY)}", micro=False
    )

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{MOCK_GATEWAY_ID}_qr_code"
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC

    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.identifiers == {("threema", MOCK_GATEWAY_ID)}
    assert device.name == mock_config_entry_with_keys.title
    assert device.model == "Gateway"

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{ENTITY_ID}")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/svg+xml"
    assert b"<svg" in await resp.read()


async def test_no_qr_code_without_private_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no QR code is created for gateways without end-to-end encryption."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.domain == "image"
    ]
