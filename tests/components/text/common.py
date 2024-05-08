"""Common test helpers for the text entity component tests."""

from typing import Any

from homeassistant.components.text import RestoreText, TextEntity


class MockTextEntity(TextEntity):
    """Mock text class."""

    def __init__(
        self, native_value="test", native_min=None, native_max=None, pattern=None
    ) -> None:
        """Initialize mock text entity."""

        self._attr_native_value = native_value
        if native_min is not None:
            self._attr_native_min = native_min
        if native_max is not None:
            self._attr_native_max = native_max
        if pattern is not None:
            self._attr_pattern = pattern

    def set_value(self, value: str) -> None:
        """Change the selected option."""
        self._attr_native_value = value


class MockRestoreText(MockTextEntity, RestoreText):
    """Mock RestoreText class."""

    def __init__(self, name: str, **values: Any) -> None:
        """Initialize the MockRestoreText."""
        super().__init__(**values)

        self._attr_name = name

    async def async_added_to_hass(self) -> None:
        """Restore native_*."""
        await super().async_added_to_hass()
        if (last_text_data := await self.async_get_last_text_data()) is None:
            return
        self._attr_native_max = last_text_data.native_max
        self._attr_native_min = last_text_data.native_min
        self._attr_native_value = last_text_data.native_value
