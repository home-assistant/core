"""The tests for vacuum platforms."""

from typing import Any

from homeassistant.components.vacuum import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_integration,
    mock_platform,
)
from tests.testing_config.custom_components.test import vacuum as VacuumPlatform


async def create_entity(
    hass: HomeAssistant,
    manifest_extra: dict[str, Any] | None,
    mock_vacuum: VacuumPlatform.MockVacuum = VacuumPlatform.MockVacuum,
    **kwargs,
) -> VacuumPlatform.MockVacuum:
    """Create the vacuum entity to run tests on."""

    vacuum_entity = mock_vacuum(
        name="Testing",
        entity_id="vacuum.testing",
        **kwargs,
    )

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_vacuum_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test vacuum platform via config entry."""
        async_add_entities([vacuum_entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
            partial_manifest=manifest_extra,
        ),
        built_in=False,
    )
    mock_platform(
        hass,
        "test.vacuum",
        MockPlatform(async_setup_entry=async_setup_entry_vacuum_platform),
    )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return vacuum_entity
