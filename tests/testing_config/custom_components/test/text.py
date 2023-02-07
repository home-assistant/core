"""Provide a mock text platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.text import RestoreText, TextEntity, TextMode

from tests.common import MockEntity

UNIQUE_TEXT = "unique_text"

ENTITIES = []


class MockTextEntity(MockEntity, TextEntity):
    """Mock text class."""

    @property
    def native_max(self):
        """Return the native native_max."""
        return self._handle("native_max")

    @property
    def native_min(self):
        """Return the native native_min."""
        return self._handle("native_min")

    @property
    def mode(self):
        """Return the mode."""
        return self._handle("mode")

    @property
    def pattern(self):
        """Return the pattern."""
        return self._handle("pattern")

    @property
    def native_value(self):
        """Return the native value of this text."""
        return self._handle("native_value")

    def set_native_value(self, value: str) -> None:
        """Change the selected option."""
        self._values["native_value"] = value


class MockRestoreText(MockTextEntity, RestoreText):
    """Mock RestoreText class."""

    async def async_added_to_hass(self) -> None:
        """Restore native_*."""
        await super().async_added_to_hass()
        if (last_text_data := await self.async_get_last_text_data()) is None:
            return
        self._values["native_max"] = last_text_data.native_max
        self._values["native_min"] = last_text_data.native_min
        self._values["native_value"] = last_text_data.native_value


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockTextEntity(
                name="test",
                native_min=1,
                native_max=5,
                mode=TextMode.TEXT,
                pattern=r"[A-Za-z0-9]",
                unique_id=UNIQUE_TEXT,
                native_value="Hello",
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
