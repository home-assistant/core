"""Test button platform for Swing2Sleep Smarla integration."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

BUTTON_ENTITIES = [
    {
        "entity_id": "button.smarla_send_diagnostics",
        "service": "system",
        "property": "send_diagnostic_data",
    },
]


@pytest.mark.usefixtures("mock_federwiege")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Smarla entities."""
    with (
        patch("homeassistant.components.smarla.PLATFORMS", [Platform.BUTTON]),
    ):
        assert await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize("entity_info", BUTTON_ENTITIES)
async def test_button_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    entity_info: dict[str, str],
) -> None:
    """Test Smarla Button press behavior."""
    assert await setup_integration(hass, mock_config_entry)

    mock_button_property = mock_federwiege.get_property(
        entity_info["service"], entity_info["property"]
    )

    entity_id = entity_info["entity_id"]

    # Turn on
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_button_property.set.assert_called_once()
