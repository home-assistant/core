"""Test the Ubiquiti airOS sensors."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airos import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_airos_entities

from tests.common import MockConfigEntry

# Mock data for various scenarios
MOCK_CONFIG = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "test_user",
    CONF_PASSWORD: "test_password",
}


@pytest.fixture
def mock_airos_client(ap_fixture: dict[str, Any]):
    """Fixture to mock the AirOS API client."""
    with patch(
        "homeassistant.components.airos.AirOS", autospec=True
    ) as mock_airos_class:
        mock_client_instance = mock_airos_class.return_value
        mock_client_instance.login.return_value = True
        mock_client_instance.status.return_value = ap_fixture
        yield mock_airos_class


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_airos_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test_entry",
        unique_id="test_unique_id",
    )
    await setup_integration(hass, config_entry)

    snapshot_airos_entities(hass, entity_registry, snapshot, Platform.SENSOR)
