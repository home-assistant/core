"""Test the Person significant change platform."""
from homeassistant.components.person.significant_change import (
    async_check_significant_change,
)


async def test_significant_change():
    """Detect Person significant changes."""
    attrs = {}
    assert not async_check_significant_change(None, "home", attrs, "home", attrs)
    assert async_check_significant_change(None, "home", attrs, "not_home", attrs)
