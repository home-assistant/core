"""Test the Lock significant change platform."""
from homeassistant.components.lock.significant_change import (
    async_check_significant_change,
)


async def test_significant_change() -> None:
    """Detect Lock significant changes."""
    old_attrs = {"attr_1": "a"}
    new_attrs = {"attr_1": "b"}

    assert (
        async_check_significant_change(None, "locked", old_attrs, "locked", old_attrs)
        is False
    )
    assert (
        async_check_significant_change(None, "locked", old_attrs, "locked", new_attrs)
        is False
    )
    assert (
        async_check_significant_change(None, "locked", old_attrs, "unlocked", old_attrs)
        is True
    )
