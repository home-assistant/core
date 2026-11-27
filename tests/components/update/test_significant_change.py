"""Test the update significant change platform."""

from homeassistant.components.update import UpdateEntityStateAttribute
from homeassistant.components.update.significant_change import (
    async_check_significant_change,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant


async def test_significant_change(hass: HomeAssistant) -> None:
    """Detect update significant changes."""
    assert async_check_significant_change(hass, STATE_ON, {}, STATE_OFF, {})
    assert async_check_significant_change(hass, STATE_OFF, {}, STATE_ON, {})
    assert not async_check_significant_change(hass, STATE_OFF, {}, STATE_OFF, {})
    assert not async_check_significant_change(hass, STATE_ON, {}, STATE_ON, {})

    attrs = {
        UpdateEntityStateAttribute.INSTALLED_VERSION: "1.0.0",
        UpdateEntityStateAttribute.IN_PROGRESS: False,
        UpdateEntityStateAttribute.LATEST_VERSION: "1.0.1",
        UpdateEntityStateAttribute.RELEASE_SUMMARY: "Fixes!",
        UpdateEntityStateAttribute.RELEASE_URL: "https://www.example.com",
        UpdateEntityStateAttribute.SKIPPED_VERSION: None,
        UpdateEntityStateAttribute.TITLE: "Piece of Software",
    }
    assert not async_check_significant_change(hass, STATE_ON, attrs, STATE_ON, attrs)

    assert async_check_significant_change(
        hass,
        STATE_ON,
        attrs,
        STATE_ON,
        attrs.copy() | {UpdateEntityStateAttribute.INSTALLED_VERSION: "1.0.1"},
    )

    assert async_check_significant_change(
        hass,
        STATE_ON,
        attrs,
        STATE_ON,
        attrs.copy() | {UpdateEntityStateAttribute.LATEST_VERSION: "1.0.2"},
    )

    assert not async_check_significant_change(
        hass,
        STATE_ON,
        attrs,
        STATE_ON,
        attrs.copy() | {UpdateEntityStateAttribute.IN_PROGRESS: True},
    )

    assert not async_check_significant_change(
        hass,
        STATE_ON,
        attrs,
        STATE_ON,
        attrs.copy() | {UpdateEntityStateAttribute.RELEASE_SUMMARY: "More fixes!"},
    )

    assert not async_check_significant_change(
        hass,
        STATE_ON,
        attrs,
        STATE_ON,
        attrs.copy()
        | {
            UpdateEntityStateAttribute.RELEASE_URL: "https://www.example.com/changed_url"
        },
    )

    assert not async_check_significant_change(
        hass,
        STATE_ON,
        attrs,
        STATE_ON,
        attrs.copy() | {UpdateEntityStateAttribute.SKIPPED_VERSION: "1.0.0"},
    )

    assert not async_check_significant_change(
        hass,
        STATE_ON,
        attrs,
        STATE_ON,
        attrs.copy() | {UpdateEntityStateAttribute.TITLE: "Renamed the software..."},
    )
