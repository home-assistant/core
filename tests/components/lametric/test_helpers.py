"""Tests for the LaMetric helpers."""

from unittest.mock import MagicMock

from demetriek import App
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.lametric.helpers import (
    async_get_coordinator_by_device_id,
    current_widget,
    widget_labels,
    widget_options,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er


async def test_get_coordinator_by_device_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_lametric: MagicMock,
) -> None:
    """Test get LaMetric coordinator by device ID ."""
    with pytest.raises(
        ServiceValidationError, match="Device with ID bla was not found"
    ):
        async_get_coordinator_by_device_id(hass, "bla")

    entry = entity_registry.async_get("button.frenck_s_lametric_next_app")
    assert entry
    assert entry.device_id

    coordinator = async_get_coordinator_by_device_id(hass, entry.device_id)
    assert coordinator.data == mock_lametric.device.return_value

    # Unload entry
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="is not loaded"):
        async_get_coordinator_by_device_id(hass, entry.device_id)


def _app(package: str, title: str, widgets: dict) -> App:
    """Return an app for testing."""
    return App.from_dict(
        {
            "package": package,
            "title": title,
            "vendor": "LaMetric",
            "version": "1.0.0",
            "version_code": "1",
            "widgets": widgets,
        }
    )


def test_widget_labels() -> None:
    """Test the ordering and naming of widget labels."""
    apps = {
        "com.a": _app(
            "com.a",
            "App A",
            {
                # No settings, so it falls back to the app title.
                "a1": {"index": 1, "package": "com.a"},
                "a2": {
                    "index": 0,
                    "package": "com.a",
                    "settings": {"_title": "Custom"},
                },
            },
        ),
        "com.b": _app("com.b", "App B", {"b1": {"index": 2, "package": "com.b"}}),
    }

    assert widget_labels(apps) == [
        ("Custom", "com.a", "a2"),
        ("App A", "com.a", "a1"),
        ("App B", "com.b", "b1"),
    ]
    assert widget_options(apps) == ["Custom", "App A", "App B"]


def test_widget_labels_duplicates() -> None:
    """Test that duplicate widget names get their position appended."""
    apps = {
        "com.a": _app(
            "com.a",
            "App A",
            {
                "a1": {
                    "index": 0,
                    "package": "com.a",
                    "settings": {"_title": "Weather"},
                },
                "a2": {
                    "index": 3,
                    "package": "com.a",
                    "settings": {"_title": "Weather"},
                },
            },
        ),
    }

    assert widget_labels(apps) == [
        ("Weather 0", "com.a", "a1"),
        ("Weather 3", "com.a", "a2"),
    ]


def test_current_widget() -> None:
    """Test resolving the widget shown on a device."""
    apps = {
        "com.a": _app(
            "com.a",
            "App A",
            {
                "a1": {"index": 0, "package": "com.a"},
                "a2": {
                    "index": 1,
                    "package": "com.a",
                    "visible": True,
                    "settings": {"_title": "Custom"},
                },
            },
        ),
    }

    assert current_widget(apps) == "Custom"


def test_current_widget_not_reported() -> None:
    """Test that no widget is reported on firmware without the flag."""
    apps = {
        "com.a": _app("com.a", "App A", {"a1": {"index": 0, "package": "com.a"}}),
    }

    assert current_widget(apps) is None
