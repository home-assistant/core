"""The tests for the WebOS TV platform."""

from unittest.mock import Mock, mock_open, patch

from aiowebostv import WebOsTvPairError

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.webostv import DOMAIN

from . import (
    MOCK_JSON,
    create_memory_sqlite_engine,
    is_entity_unique_id_updated,
    setup_legacy_component,
)


async def test_missing_keys_file_abort(hass, client, caplog):
    """Test abort import when no pairing keys file."""
    with patch(
        "homeassistant.components.webostv.os.path.isfile", Mock(return_value=False)
    ):
        await setup_legacy_component(hass)

    assert "No pairing keys, Not importing" in caplog.text
    assert not is_entity_unique_id_updated(hass)


async def test_empty_json_abort(hass, client, caplog):
    """Test abort import when keys file is empty."""
    m_open = mock_open(read_data="[]")

    with patch(
        "homeassistant.components.webostv.os.path.isfile", Mock(return_value=True)
    ), patch("homeassistant.components.webostv.open", m_open, create=True):
        await setup_legacy_component(hass)

    assert "No pairing keys, Not importing" in caplog.text
    assert not is_entity_unique_id_updated(hass)


async def test_valid_json_migrate_not_needed(hass, client, caplog):
    """Test import from valid json entity already migrated or removed."""
    m_open = mock_open(read_data=MOCK_JSON)

    with patch(
        "homeassistant.components.webostv.os.path.isfile", Mock(return_value=True)
    ), patch("homeassistant.components.webostv.open", m_open, create=True):
        await setup_legacy_component(hass, False)

    assert "Migrating webOS Smart TV entity" not in caplog.text
    assert not is_entity_unique_id_updated(hass)


async def test_valid_json_missing_host_key(hass, client, caplog):
    """Test import from valid json missing host key."""
    m_open = mock_open(read_data='{"1.2.3.5": "other-key"}')

    with patch(
        "homeassistant.components.webostv.os.path.isfile", Mock(return_value=True)
    ), patch("homeassistant.components.webostv.open", m_open, create=True):
        await setup_legacy_component(hass)

    assert "Not importing webOS Smart TV host" in caplog.text
    assert not is_entity_unique_id_updated(hass)


async def test_not_connected_import(hass, client, caplog, monkeypatch):
    """Test import while device is not connected."""
    m_open = mock_open(read_data=MOCK_JSON)
    monkeypatch.setattr(client, "is_connected", Mock(return_value=False))
    monkeypatch.setattr(client, "connect", Mock(side_effect=OSError))

    with patch(
        "homeassistant.components.webostv.os.path.isfile", Mock(return_value=True)
    ), patch("homeassistant.components.webostv.open", m_open, create=True):
        await setup_legacy_component(hass)

    assert f"Please make sure webOS TV {MP_DOMAIN}.{DOMAIN}" in caplog.text
    assert not is_entity_unique_id_updated(hass)


async def test_pair_error_import_abort(hass, client, caplog, monkeypatch):
    """Test abort import if device is not paired."""
    m_open = mock_open(read_data=MOCK_JSON)
    monkeypatch.setattr(client, "is_connected", Mock(return_value=False))
    monkeypatch.setattr(client, "connect", Mock(side_effect=WebOsTvPairError))

    with patch(
        "homeassistant.components.webostv.os.path.isfile", Mock(return_value=True)
    ), patch("homeassistant.components.webostv.open", m_open, create=True):
        await setup_legacy_component(hass)

    assert f"Please make sure webOS TV {MP_DOMAIN}.{DOMAIN}" not in caplog.text
    assert not is_entity_unique_id_updated(hass)


async def test_entity_removed_import_abort(hass, client_entity_removed, caplog):
    """Test abort import if entity removed by user during import."""
    m_open = mock_open(read_data=MOCK_JSON)

    with patch(
        "homeassistant.components.webostv.os.path.isfile", Mock(return_value=True)
    ), patch("homeassistant.components.webostv.open", m_open, create=True):
        await setup_legacy_component(hass)

    assert "Not updating webOSTV Smart TV entity" in caplog.text
    assert not is_entity_unique_id_updated(hass)


async def test_json_import(hass, client, caplog, monkeypatch):
    """Test import from json keys file."""
    m_open = mock_open(read_data=MOCK_JSON)
    monkeypatch.setattr(client, "is_connected", Mock(return_value=True))
    monkeypatch.setattr(client, "connect", Mock(return_value=True))

    with patch(
        "homeassistant.components.webostv.os.path.isfile", Mock(return_value=True)
    ), patch("homeassistant.components.webostv.open", m_open, create=True):
        await setup_legacy_component(hass)

    assert "imported from YAML config" in caplog.text
    assert is_entity_unique_id_updated(hass)


async def test_sqlite_import(hass, client, caplog, monkeypatch):
    """Test import from sqlite keys file."""
    m_open = mock_open(read_data="will raise JSONDecodeError")
    monkeypatch.setattr(client, "is_connected", Mock(return_value=True))
    monkeypatch.setattr(client, "connect", Mock(return_value=True))

    with patch(
        "homeassistant.components.webostv.os.path.isfile", Mock(return_value=True)
    ), patch("homeassistant.components.webostv.open", m_open, create=True), patch(
        "homeassistant.components.webostv.db.create_engine",
        side_effect=create_memory_sqlite_engine,
    ):
        await setup_legacy_component(hass)

    assert "imported from YAML config" in caplog.text
    assert is_entity_unique_id_updated(hass)
