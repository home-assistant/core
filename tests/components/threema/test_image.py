"""Test the Threema Gateway image platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_qr_code_entity_created(
    hass: HomeAssistant,
    mock_config_entry_with_keys: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test QR code entity is created when public key is present."""
    mock_config_entry_with_keys.add_to_hass(hass)

    with patch("homeassistant.components.threema.image.qrcode.QRCode") as mock_qr_class:
        mock_qr = MagicMock()
        mock_qr_class.return_value = mock_qr
        mock_img = MagicMock()
        mock_qr.make_image.return_value = mock_img
        mock_img.save = MagicMock(
            side_effect=lambda buf, **kwargs: buf.write(b"fake_png_data")
        )

        await hass.config_entries.async_setup(mock_config_entry_with_keys.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_with_keys.entry_id
    )
    image_entities = [e for e in entities if e.domain == "image"]
    assert len(image_entities) == 1
    assert image_entities[0].unique_id == "*TESTGWY_qr_code"


async def test_qr_code_entity_not_created_without_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test QR code entity is NOT created when no public key."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    image_entities = [e for e in entities if e.domain == "image"]
    assert len(image_entities) == 0


async def test_qr_code_image_available(
    hass: HomeAssistant,
    mock_config_entry_with_keys: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test QR code entity is available when image is generated."""
    mock_config_entry_with_keys.add_to_hass(hass)

    with patch("homeassistant.components.threema.image.qrcode.QRCode") as mock_qr_class:
        mock_qr = MagicMock()
        mock_qr_class.return_value = mock_qr
        mock_img = MagicMock()
        mock_qr.make_image.return_value = mock_img
        mock_img.save = MagicMock(
            side_effect=lambda buf, **kwargs: buf.write(b"fake_png_data")
        )

        await hass.config_entries.async_setup(mock_config_entry_with_keys.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_with_keys.entry_id
    )
    image_entities = [e for e in entities if e.domain == "image"]
    assert len(image_entities) == 1

    state = hass.states.get(image_entities[0].entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
