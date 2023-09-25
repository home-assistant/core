"""Test helpers for image_processing."""
from collections.abc import Generator

import pytest

from homeassistant.components import image_processing
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


class MockImageProcessingEntity(image_processing.ImageProcessingEntity):
    """Mock image entity."""

    _attr_name = "Test"


class MockImageProcessingConfigEntry:
    """A mock image config entry."""

    def __init__(self, entities: list[image_processing.ImageProcessingEntity]) -> None:
        """Initialize."""
        self._entities = entities

    async def async_setup_entry(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test image platform via config entry."""
        async_add_entities([self._entities])


class MockImageProcessingPlatform:
    """A mock image platform."""

    PLATFORM_SCHEMA = image_processing.PLATFORM_SCHEMA

    def __init__(self, entities: list[image_processing.ImageProcessingEntity]) -> None:
        """Initialize."""
        self._entities = entities

    async def async_setup_platform(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up the mock image platform."""
        async_add_entities(self._entities)


@pytest.fixture(name="config_flow")
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""

    class MockFlow(ConfigFlow):
        """Test flow."""

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture(name="mock_image_processing_config_entry")
async def mock_image_processing_config_entry_fixture(
    hass: HomeAssistant, config_flow: None
) -> ConfigEntry:
    """Initialize a mock image config_entry."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(
            config_entry, image_processing.DOMAIN
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload test config entry."""
        await hass.config_entries.async_forward_entry_unload(
            config_entry, image_processing.DOMAIN
        )
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{image_processing.DOMAIN}",
        MockImageProcessingConfigEntry(MockImageProcessingEntity()),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
