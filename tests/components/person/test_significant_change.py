"""Test the Person significant change platform."""

from homeassistant.components.person.significant_change import (
    async_check_significant_change,
)


async def test_significant_change() -> None:
    """Detect Person significant changes and ensure that attribute changes do not trigger a significant change."""
    old_attrs = {"source": "device_tracker.wifi_device"}
    new_attrs = {"source": "device_tracker.gps_device"}
    assert not async_check_significant_change(
        None, "home", old_attrs, "home", new_attrs
    )
    assert async_check_significant_change(
        None, "home", new_attrs, "not_home", new_attrs
    )
