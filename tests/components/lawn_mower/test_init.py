"""The tests for the lawn mower integration."""
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


class MockFlow(ConfigFlow):
    """Test flow."""


class MockLawnMowerEntity(LawnMowerEntity):
    """Mock lawn mower device to use in tests."""

    def __init__(
        self,
        unique_id: str = "mock_lawn_mower",
        name: str = "Lawn Mower",
        features: LawnMowerEntityFeature = LawnMowerEntityFeature(0),
    ) -> None:
        """Initialize the lawn mower."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_supported_features = features

    def start_mowing(self) -> None:
        """Start mowing."""
        self._attr_activity = LawnMowerActivity.MOWING


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


async def test_lawn_mower_setup(hass: HomeAssistant) -> None:
    """Test setup and tear down of lawn mower platform and entity."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(
            config_entry, Platform.LAWN_MOWER
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload up test config entry."""
        await hass.config_entries.async_unload_platforms(
            config_entry, [Platform.LAWN_MOWER]
        )
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )

    entity1 = LawnMowerEntity()
    entity1.entity_id = "lawn_mower.mock_lawn_mower"

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test platform via config entry."""
        async_add_entities([entity1])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{LAWN_MOWER_DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert hass.states.get(entity1.entity_id)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_sync_start_mowing(hass: HomeAssistant) -> None:
    """Test if async mowing calls sync mowing."""
    lawn_mower = MockLawnMowerEntity()
    lawn_mower.hass = hass

    lawn_mower.start_mowing = MagicMock()
    await lawn_mower.async_start_mowing()

    assert lawn_mower.start_mowing.called


async def test_sync_dock(hass: HomeAssistant) -> None:
    """Test if async dock calls sync dock."""
    lawn_mower = MockLawnMowerEntity()
    lawn_mower.hass = hass

    lawn_mower.dock = MagicMock()
    await lawn_mower.async_dock()

    assert lawn_mower.dock.called


async def test_sync_pause(hass: HomeAssistant) -> None:
    """Test if async pause calls sync pause."""
    lawn_mower = MockLawnMowerEntity()
    lawn_mower.hass = hass

    lawn_mower.pause = MagicMock()
    await lawn_mower.async_pause()

    assert lawn_mower.pause.called


async def test_lawn_mower_default(hass: HomeAssistant) -> None:
    """Test lawn mower entity with defaults."""
    lawn_mower = MockLawnMowerEntity()
    lawn_mower.hass = hass

    assert lawn_mower.state is None


async def test_lawn_mower_state(hass: HomeAssistant) -> None:
    """Test lawn mower entity returns state."""
    lawn_mower = MockLawnMowerEntity(
        "lawn_mower_1", "Test lawn mower", LawnMowerActivity.MOWING
    )
    lawn_mower.hass = hass
    lawn_mower.start_mowing()

    assert lawn_mower.state == str(LawnMowerActivity.MOWING)
