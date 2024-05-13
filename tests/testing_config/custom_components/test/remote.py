"""Provide a mock remote platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.remote import RemoteEntity
from homeassistant.const import STATE_OFF, STATE_ON

from tests.common import MockToggleEntity

ENTITIES = []


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockRemote("TV", STATE_ON),
            MockRemote("DVD", STATE_OFF),
            MockRemote(None, STATE_OFF),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)


class MockRemote(MockToggleEntity, RemoteEntity):
    """Mock remote class."""

    supported_features = 0
