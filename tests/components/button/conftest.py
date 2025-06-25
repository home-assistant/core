"""Fixtures for the button entity component tests."""

import logging

import pytest

from homeassistant.components.button import DOMAIN, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import TEST_DOMAIN

from tests.common import MockEntity, MockPlatform, mock_platform

_LOGGER = logging.getLogger(__name__)


class MockButtonEntity(MockEntity, ButtonEntity):
    """Mock Button class."""

    def press(self) -> None:
        """Press the button."""
        _LOGGER.info("The button has been pressed")


@pytest.fixture
async def setup_platform(hass: HomeAssistant) -> None:
    """Set up the button entity platform."""

    async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddConfigEntryEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up test button platform."""
        async_add_entities(
            [
                MockButtonEntity(
                    name="button 1",
                    unique_id="unique_button_1",
                ),
            ]
        )

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_platform=async_setup_platform),
    )
