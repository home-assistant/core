"""Test helpers for image."""

from collections.abc import Generator

import pytest

from homeassistant.components import image
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


class MockImageEntity(image.ImageEntity):
    """Mock image entity."""

    _attr_name = "Test"

    async def async_added_to_hass(self):
        """Set the update time."""
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return b"Test"


class MockImageEntityInvalidContentType(image.ImageEntity):
    """Mock image entity."""

    _attr_name = "Test"

    async def async_added_to_hass(self):
        """Set the update time and assign and incorrect content type."""
        self._attr_content_type = "text/json"
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return b"Test"


class MockImageEntityCapitalContentType(image.ImageEntity):
    """Mock image entity with correct content type, but capitalized."""

    _attr_name = "Test"

    async def async_added_to_hass(self):
        """Set the update time and assign and incorrect content type."""
        self._attr_content_type = "Image/jpeg"
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return b"Test"


class MockURLImageEntity(image.ImageEntity):
    """Mock image entity."""

    _attr_image_url = "https://example.com/myimage.jpg"
    _attr_name = "Test"

    async def async_added_to_hass(self):
        """Set the update time."""
        self._attr_image_last_updated = dt_util.utcnow()


class MockImageNoStateEntity(image.ImageEntity):
    """Mock image entity."""

    _attr_name = "Test"

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return b"Test"


class MockImageNoDataEntity(image.ImageEntity):
    """Mock image entity."""

    _attr_name = "Test"

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return None


class MockImageSyncEntity(image.ImageEntity):
    """Mock image entity."""

    _attr_name = "Test"

    async def async_added_to_hass(self):
        """Set the update time."""
        self._attr_image_last_updated = dt_util.utcnow()

    def image(self) -> bytes | None:
        """Return bytes of image."""
        return b"Test"


class MockImageConfigEntry:
    """A mock image config entry."""

    def __init__(self, entities: list[image.ImageEntity]) -> None:
        """Initialize."""
        self._entities = entities

    async def async_setup_entry(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test image platform via config entry."""
        async_add_entities([self._entities])


class MockImagePlatform:
    """A mock image platform."""

    PLATFORM_SCHEMA = image.PLATFORM_SCHEMA

    def __init__(self, entities: list[image.ImageEntity]) -> None:
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
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""

    class MockFlow(ConfigFlow):
        """Test flow."""

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture(name="mock_image_config_entry")
async def mock_image_config_entry_fixture(
    hass: HomeAssistant, config_flow: None
) -> ConfigEntry:
    """Initialize a mock image config_entry."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [image.DOMAIN]
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload test config entry."""
        await hass.config_entries.async_unload_platforms(config_entry, [image.DOMAIN])
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
        f"{TEST_DOMAIN}.{image.DOMAIN}",
        MockImageConfigEntry(MockImageEntity(hass)),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="mock_image_platform")
async def mock_image_platform_fixture(hass: HomeAssistant) -> None:
    """Initialize a mock image platform."""
    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.image", MockImagePlatform([MockImageEntity(hass)]))
    assert await async_setup_component(
        hass, image.DOMAIN, {"image": {"platform": "test"}}
    )
    await hass.async_block_till_done()
