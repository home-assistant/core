"""Tests for the Heos component."""

from homeassistant.components.heos.coordinator import HeosCoordinator

from tests.common import MockConfigEntry


class MockHeosConfigEntry(MockConfigEntry):
    """Define a mock HEOS config entry."""

    runtime_data: HeosCoordinator
