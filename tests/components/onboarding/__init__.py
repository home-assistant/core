"""Tests for the onboarding component."""

from homeassistant.components import onboarding


def mock_storage(hass_storage, data):
    """Mock the onboarding storage."""
    hass_storage[onboarding.STORAGE_KEY] = {
        'version': onboarding.STORAGE_VERSION,
        'data': data
    }
