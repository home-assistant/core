"""Shared fixtures for Synology SRM tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.synology_srm.const import DOMAIN
from homeassistant.const import CONF_HOST

from . import DEVICE_1, MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture
def mock_synology_client() -> Generator[MagicMock]:
    """Patch synology_srm.Client at the module level."""
    client = MagicMock()
    client.mesh.get_system_info.return_value = {"model": "RT2600ac"}
    client.core.get_network_nsm_device.return_value = [DEVICE_1]
    with patch("synology_srm.Client", return_value=client) as client_cls:
        client_cls.return_value = client
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A non-added config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_CONFIG[CONF_HOST]
    )
