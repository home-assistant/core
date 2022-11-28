"""The tests for the text component."""
import pytest

from homeassistant.components.text import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_PATTERN,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_SET_VALUE,
    TextEntity,
    TextMode,
    _async_set_value,
)
from homeassistant.const import MAX_LENGTH_STATE_STATE
from homeassistant.core import ServiceCall


class MockTextEntity(TextEntity):
    """Mock text device to use in tests."""

    def __init__(
        self, native_value="test", native_min=None, native_max=None, pattern=None
    ):
        """Initialize mock text entity."""
        self._attr_native_value = native_value
        if native_min is not None:
            self._attr_native_min = native_min
        if native_max is not None:
            self._attr_native_max = native_max
        if pattern is not None:
            self._attr_pattern = pattern

    async def async_set_value(self, value: str) -> None:
        """Set the value of the text."""
        self._attr_native_value = value


async def test_text_default(hass):
    """Test text entity with defaults."""
    text = MockTextEntity()
    text.hass = hass

    assert text.capability_attributes == {
        ATTR_MIN: 0,
        ATTR_MAX: MAX_LENGTH_STATE_STATE,
        ATTR_MODE: TextMode.TEXT,
        ATTR_PATTERN: None,
    }
    assert text.pattern is None
    assert text.state == "test"


async def test_text_new_min_max_pattern(hass):
    """Test text entity with new min, max, and pattern."""
    text = MockTextEntity(native_min=-1, native_max=500, pattern=r"[a-z]")
    text.hass = hass

    assert text.capability_attributes == {
        ATTR_MIN: 0,
        ATTR_MAX: MAX_LENGTH_STATE_STATE,
        ATTR_MODE: TextMode.TEXT,
        ATTR_PATTERN: r"[a-z]",
    }


async def test_text_set_value(hass):
    """Test text entity with set_value service."""
    text = MockTextEntity(native_min=1, native_max=5, pattern=r"[a-z]")
    text.hass = hass

    with pytest.raises(ValueError):
        await _async_set_value(
            text, ServiceCall(DOMAIN, SERVICE_SET_VALUE, {ATTR_VALUE: ""})
        )

    with pytest.raises(ValueError):
        await _async_set_value(
            text, ServiceCall(DOMAIN, SERVICE_SET_VALUE, {ATTR_VALUE: "hello world!"})
        )

    with pytest.raises(ValueError):
        await _async_set_value(
            text, ServiceCall(DOMAIN, SERVICE_SET_VALUE, {ATTR_VALUE: "HELLO"})
        )

    await _async_set_value(
        text, ServiceCall(DOMAIN, SERVICE_SET_VALUE, {ATTR_VALUE: "test2"})
    )

    assert text.state == "test2"


async def test_text_value_outside_bounds(hass):
    """Test text entity with value that is outside min and max."""
    with pytest.raises(ValueError):
        MockTextEntity(
            "hello world", native_min=2, native_max=5, pattern=r"[a-z]"
        ).state
    with pytest.raises(ValueError):
        MockTextEntity(
            "hello world", native_min=15, native_max=20, pattern=r"[a-z]"
        ).state
