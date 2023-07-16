"""The tests for the lawn mower integration."""
from unittest.mock import MagicMock

from homeassistant.components.lawn_mower import LawnMowerEntity, LawnMowerEntityFeature
from homeassistant.core import HomeAssistant


class MockLawnMowerEntity(LawnMowerEntity):
    """Mock lawn mower device to use in tests."""

    @property
    def supported_features(self) -> LawnMowerEntityFeature:
        """Return the list of features."""
        return 0


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


async def test_sync_enable_schedule(hass: HomeAssistant) -> None:
    """Test if async schedule calls sync schedule."""
    lawn_mower = MockLawnMowerEntity()
    lawn_mower.hass = hass

    lawn_mower.enable_schedule = MagicMock()
    await lawn_mower.async_enable_schedule()

    assert lawn_mower.enable_schedule.called


async def test_sync_disable_schedule(hass: HomeAssistant) -> None:
    """Test if async disable calls sync disable."""
    lawn_mower = MockLawnMowerEntity()
    lawn_mower.hass = hass

    lawn_mower.disable_schedule = MagicMock()
    await lawn_mower.async_disable_schedule()

    assert lawn_mower.disable_schedule.called


async def test_lawn_mower_default(hass: HomeAssistant) -> None:
    """Test lawn mower entity with defaults."""
    lawn_mower = MockLawnMowerEntity()
    lawn_mower.hass = hass

    assert lawn_mower.state is None
