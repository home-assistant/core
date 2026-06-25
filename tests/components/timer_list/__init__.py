"""Tests for the Timer list integration."""

from homeassistant.components.timer_list import TimerListEntity
from homeassistant.components.timer_list.const import DOMAIN, TimerListEntityFeature
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from tests.common import MockConfigEntry, MockPlatform, mock_platform

TEST_DOMAIN = "test"

ALL_FEATURES = (
    TimerListEntityFeature.START_TIMER
    | TimerListEntityFeature.PAUSE_TIMER
    | TimerListEntityFeature.CANCEL_TIMER
    | TimerListEntityFeature.ADD_TIME
)


class MockFlow(ConfigFlow):
    """Test flow."""


class MockTimerListEntity(TimerListEntity):
    """Test timer list entity."""

    _attr_supported_features = ALL_FEATURES

    def __init__(self, name: str = "Timers") -> None:
        """Initialize entity."""
        super().__init__()
        self._attr_name = name


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
