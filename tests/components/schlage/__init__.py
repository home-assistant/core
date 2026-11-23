"""Tests for the Schlage integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.schlage.coordinator import SchlageDataUpdateCoordinator

type MockSchlageConfigEntry = MockConfigEntry[SchlageDataUpdateCoordinator]
