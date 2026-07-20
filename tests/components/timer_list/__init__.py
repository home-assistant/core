"""Tests for the Timer list integration."""

from homeassistant.components.timer_list import (
    DOMAIN,
    InMemoryTimerListEntity,
    TimerListEntity,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import ulid as ulid_util

from tests.common import MockConfigEntry, MockPlatform, mock_platform

TEST_DOMAIN = "test"


class MockFlow(ConfigFlow):
    """Test flow."""


class MockTimerListEntity(InMemoryTimerListEntity):
    """Test timer list entity.

    Subclasses the reference ``InMemoryTimerListEntity`` so the generic
    services, websocket API, and triggers are exercised against the real
    storage/scheduling logic without depending on the ``local_timer_list``
    integration.
    """

    def __init__(self, name: str = "Timers") -> None:
        """Initialize entity."""
        super().__init__(name=name, unique_id=ulid_util.ulid_now())


async def create_mock_platform(
    hass: HomeAssistant,
    entities: list[TimerListEntity],
) -> MockConfigEntry:
    """Create a timer_list platform with the specified entities."""

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test timer_list platform via config entry."""
        async_add_entities(entities)

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
