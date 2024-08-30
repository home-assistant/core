"""Test helpers for Assist Satellite."""

from unittest.mock import Mock

import pytest

from homeassistant.components.assist_pipeline import PipelineEvent
from homeassistant.components.assist_satellite import (
    DOMAIN as AS_DOMAIN,
    AssistSatelliteEntity,
    AssistSatelliteEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test_satellite"


class MockAssistSatellite(AssistSatelliteEntity):
    """Mock Assist Satellite Entity."""

    _attr_name = "Test Entity"
    _attr_supported_features = AssistSatelliteEntityFeature.ANNOUNCE

    def __init__(self) -> None:
        """Initialize the mock entity."""
        self.events = []
        self.announcements = []

    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Handle pipeline events."""
        self.events.append(event)

    async def async_announce(self, text: str, media_id: str) -> None:
        """Announce media on a device."""
        self.announcements.append((text, media_id))


@pytest.fixture
def entity() -> MockAssistSatellite:
    """Mock Assist Satellite Entity."""
    return MockAssistSatellite()


@pytest.fixture
def config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Mock config entry."""
    entry = MockConfigEntry(domain=TEST_DOMAIN)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def init_components(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity: MockAssistSatellite,
) -> None:
    """Initialize components."""
    assert await async_setup_component(hass, "homeassistant", {})

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [AS_DOMAIN])
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload test config entry."""
        await hass.config_entries.async_forward_entry_unload(config_entry, AS_DOMAIN)
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", Mock())

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test satellite platform via config entry."""
        async_add_entities([entity])

    loaded_platform = MockPlatform(async_setup_entry=async_setup_entry_platform)
    mock_platform(hass, f"{TEST_DOMAIN}.{AS_DOMAIN}", loaded_platform)

    with mock_config_flow(TEST_DOMAIN, ConfigFlow):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
