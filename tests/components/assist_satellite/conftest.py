"""Common fixtures for the Assist satellite tests."""

from collections.abc import Generator

import pytest

from homeassistant.components import assist_satellite
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.setup import async_setup_component

from . import MockSatelliteEntity

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


async def mock_config_entry_setup(
    hass: HomeAssistant, satellite_entity: MockSatelliteEntity
) -> MockConfigEntry:
    """Set up a test satellite platform via config entry."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [assist_satellite.DOMAIN]
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload test config entry."""
        await hass.config_entries.async_forward_entry_unload(
            config_entry, assist_satellite.DOMAIN
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

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test tts platform via config entry."""
        async_add_entities([satellite_entity])

    loaded_platform = MockPlatform(async_setup_entry=async_setup_entry_platform)
    mock_platform(hass, f"{TEST_DOMAIN}.{assist_satellite.DOMAIN}", loaded_platform)

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


class AssistSatelliteFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, AssistSatelliteFlow):
        yield


@pytest.fixture
def setup_mock_satellite_entity() -> MockSatelliteEntity:
    """Test satellite entity."""
    return MockSatelliteEntity()


@pytest.fixture
async def mock_satellite(
    hass: HomeAssistant, setup_mock_satellite_entity: MockSatelliteEntity
) -> MockSatelliteEntity:
    """Create a config entry."""
    assert await async_setup_component(hass, "homeassistant", {})
    await mock_config_entry_setup(hass, setup_mock_satellite_entity)
    return setup_mock_satellite_entity
