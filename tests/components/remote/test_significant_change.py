"""Test the Remote significant change platform."""
from homeassistant.components.remote import ATTR_ACTIVITY_LIST, ATTR_CURRENT_ACTIVITY
from homeassistant.components.remote.significant_change import (
    async_check_significant_change,
)


async def test_significant_change() -> None:
    """Detect Remote significant changes."""
    # no change at all
    attrs = {
        ATTR_CURRENT_ACTIVITY: "playing",
        ATTR_ACTIVITY_LIST: ["playing", "paused"],
    }
    assert not async_check_significant_change(None, "on", attrs, "on", attrs)

    # change of state is significant
    assert async_check_significant_change(None, "on", attrs, "off", attrs)

    # change of current activity is significant
    attrs = {
        "old": {
            ATTR_CURRENT_ACTIVITY: "playing",
            ATTR_ACTIVITY_LIST: ["playing", "paused"],
        },
        "new": {
            ATTR_CURRENT_ACTIVITY: "paused",
            ATTR_ACTIVITY_LIST: ["playing", "paused"],
        },
    }
    assert async_check_significant_change(None, "on", attrs["old"], "on", attrs["new"])

    # change of list of possible activities is not significant
    attrs = {
        "old": {
            ATTR_CURRENT_ACTIVITY: "playing",
            ATTR_ACTIVITY_LIST: ["playing", "paused"],
        },
        "new": {
            ATTR_CURRENT_ACTIVITY: "playing",
            ATTR_ACTIVITY_LIST: ["playing"],
        },
    }
    assert not async_check_significant_change(
        None, "on", attrs["old"], "on", attrs["new"]
    )

    # change of any not official attribute is not significant
    attrs = {
        "old": {
            ATTR_CURRENT_ACTIVITY: "playing",
            ATTR_ACTIVITY_LIST: ["playing", "paused"],
        },
        "new": {
            ATTR_CURRENT_ACTIVITY: "playing",
            ATTR_ACTIVITY_LIST: ["playing", "paused"],
            "not_official": "changed",
        },
    }
    assert not async_check_significant_change(
        None, "on", attrs["old"], "on", attrs["new"]
    )
