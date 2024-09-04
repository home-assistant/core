"""Test ViCare migration."""

from unittest.mock import patch

from homeassistant.components.vicare.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MODULE
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry


# Entity migration test can be removed in 2025.3.0
async def test_climate_entity_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the climate entity unique_id gets migrated correctly."""
    fixtures: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]
    with (
        patch(f"{MODULE}.vicare_login", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.CLIMATE]),
    ):
        mock_config_entry.add_to_hass(hass)

        entry = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway0-0",
            translation_key="heating",
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entry.entity_id).unique_id
        == "gateway0_deviceSerialVitodens300W-heating-0"
    )
