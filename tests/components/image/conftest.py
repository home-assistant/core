"""Test helpers for image."""

import pytest

from homeassistant.components import image
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockModule, mock_integration, mock_platform


class MockImageEntity(image.ImageEntity):
    """Mock image entity."""

    _attr_name = "Test"

    async def async_added_to_hass(self):
        """Set the update time."""
        self._attr_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return b"Test"


class MockImage:
    """A mock image platform."""

    PLATFORM_SCHEMA = image.PLATFORM_SCHEMA

    async def async_setup_platform(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up the mock image platform."""
        async_add_entities(
            [
                MockImageEntity(),
            ]
        )


@pytest.fixture(name="mock_image")
async def mock_image_fixture(hass: HomeAssistant):
    """Initialize a mock image platform."""
    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.image", MockImage())
    assert await async_setup_component(
        hass, image.DOMAIN, {"image": {"platform": "test"}}
    )
    await hass.async_block_till_done()
