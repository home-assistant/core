"""Configuration for Kira tests."""

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from homeassistant.components.kira import sensor as kira


@pytest.fixture
def test_config():
    """Test config."""
    return {kira.DOMAIN: {"sensors": [{"host": "127.0.0.1", "port": 17324}]}}


@pytest.fixture
def discovery_info():
    """Discovery info."""
    return {"name": "kira", "device": "kira"}


@dataclass
class FakeKiraDevices:
    """Container for devices that should be correctly set by kira integration."""

    devices: list[int] = field(default_factory=list)

    def add_entities(self, devices):
        """Mock add devices."""
        entity_id = "kira.entity_id"
        for device in devices:
            device.entity_id = entity_id
            self.devices.append(device)


@pytest.fixture()
def fake_entities():
    """Fake entities."""
    return FakeKiraDevices()


@pytest.fixture
def configured_kira(hass, test_config, discovery_info, fake_entities):
    """Configure kira platform."""
    mock_kira = MagicMock()
    hass.data[kira.DOMAIN] = {kira.CONF_SENSOR: {}}
    hass.data[kira.DOMAIN][kira.CONF_SENSOR]["kira"] = mock_kira
    kira.setup_platform(hass, test_config, fake_entities.add_entities, discovery_info)
