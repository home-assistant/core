"""Provide a mock select platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.select import SelectEntity

from tests.common import MockEntity

UNIQUE_SELECT_1 = "unique_select_1"
UNIQUE_SELECT_2 = "unique_select_2"

ENTITIES = []


class MockSelectEntity(MockEntity, SelectEntity):
    """Mock Select class."""

    _attr_current_option = None

    @property
    def current_option(self):
        """Return the current option of this select."""
        return self._handle("current_option")

    @property
    def options(self) -> list:
        """Return the list of available options of this select."""
        return self._handle("options")

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockSelectEntity(
                name="select 1",
                unique_id="unique_select_1",
                options=["option 1", "option 2", "option 3"],
                current_option="option 1",
            ),
            MockSelectEntity(
                name="select 2",
                unique_id="unique_select_2",
                options=["option 1", "option 2", "option 3"],
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
