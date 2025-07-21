"""Test the Ubiquiti airOS sensors."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airos.const import DOMAIN
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
