"""Tests for the Arcam Solo base entity."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.arcam_solo.entity import ArcamSoloEntity
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry


def test_entity_available_and_unique_id() -> None:
    """Test base entity availability and unique id."""
    entry = MockConfigEntry(domain="arcam_solo", data={CONF_NAME: "Lounge"})
    entry.runtime_data = MagicMock()
    entry.runtime_data.available = True
    entry.runtime_data.zones = {}

    entity = ArcamSoloEntity(entry, "media_player")

    assert entity.available is True
    assert entity.unique_id == f"{entry.entry_id}_media_player"


def test_entity_device_info_with_versions() -> None:
    """Test device info when versions are provided."""
    entry = MockConfigEntry(domain="arcam_solo", data={CONF_NAME: "Lounge"})
    entry.runtime_data = MagicMock()
    entry.runtime_data.available = True
    entry.runtime_data.zones = {
        1: {"software_version": "1.2.3", "rs232_version": "2.3.4"}
    }

    entity = ArcamSoloEntity(entry, "media_player")
    info = entity.device_info

    assert info["manufacturer"] == "Arcam"
    assert info["model"] == "Solo"
    assert info["name"] == "Lounge"
    assert info["sw_version"] == "1.2.3"
    assert info["hw_version"] == "2.3.4"


def test_entity_device_info_without_versions() -> None:
    """Test device info falls back to unknown versions."""
    entry = MockConfigEntry(domain="arcam_solo", data={CONF_NAME: "Lounge"})
    entry.runtime_data = MagicMock()
    entry.runtime_data.available = False
    entry.runtime_data.zones = {}

    entity = ArcamSoloEntity(entry, "media_player")
    info = entity.device_info

    assert info["sw_version"] == "Unknown"
    assert info["hw_version"] == "Unknown"
