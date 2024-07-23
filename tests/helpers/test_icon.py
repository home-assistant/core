"""Test Home Assistant icon util methods."""

import pathlib
from unittest.mock import Mock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import icon
from homeassistant.loader import IntegrationNotFound
from homeassistant.setup import async_setup_component


def test_battery_icon() -> None:
    """Test icon generator for battery sensor."""
    assert icon.icon_for_battery_level(None, True) == "mdi:battery-unknown"
    assert icon.icon_for_battery_level(None, False) == "mdi:battery-unknown"

    assert icon.icon_for_battery_level(5, True) == "mdi:battery-outline"
    assert icon.icon_for_battery_level(5, False) == "mdi:battery-alert"

    assert icon.icon_for_battery_level(100, True) == "mdi:battery-charging-100"
    assert icon.icon_for_battery_level(100, False) == "mdi:battery"

    iconbase = "mdi:battery"
    for level in range(0, 100, 5):
        print(  # noqa: T201
            "Level: %d. icon: %s, charging: %s"
            % (
                level,
                icon.icon_for_battery_level(level, False),
                icon.icon_for_battery_level(level, True),
            )
        )
        if level <= 10:
            postfix_charging = "-outline"
        elif level <= 30:
            postfix_charging = "-charging-20"
        elif level <= 50:
            postfix_charging = "-charging-40"
        elif level <= 70:
            postfix_charging = "-charging-60"
        elif level <= 90:
            postfix_charging = "-charging-80"
        else:
            postfix_charging = "-charging-100"
        if 5 < level < 95:
            postfix = f"-{int(round(level / 10 - 0.01)) * 10}"
        elif level <= 5:
            postfix = "-alert"
        else:
            postfix = ""
        assert iconbase + postfix == icon.icon_for_battery_level(level, False)
        assert iconbase + postfix_charging == icon.icon_for_battery_level(level, True)


def test_signal_icon() -> None:
    """Test icon generator for signal sensor."""
    assert icon.icon_for_signal_level(None) == "mdi:signal-cellular-outline"
    assert icon.icon_for_signal_level(0) == "mdi:signal-cellular-outline"
    assert icon.icon_for_signal_level(5) == "mdi:signal-cellular-1"
    assert icon.icon_for_signal_level(40) == "mdi:signal-cellular-2"
    assert icon.icon_for_signal_level(80) == "mdi:signal-cellular-3"
    assert icon.icon_for_signal_level(100) == "mdi:signal-cellular-3"


def test_load_icons_files(hass: HomeAssistant) -> None:
    """Test the load icons files function."""
    file1 = hass.config.path("custom_components", "test", "icons.json")
    file2 = hass.config.path("custom_components", "test", "invalid.json")
    assert icon._load_icons_files({"test": file1, "invalid": file2}) == {
        "test": {
            "entity": {
                "switch": {
                    "something": {
                        "state": {"away": "mdi:home-outline", "home": "mdi:home"}
                    }
                }
            },
        },
        "invalid": {},
    }


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_get_icons(hass: HomeAssistant) -> None:
    """Test the get icon helper."""
    icons = await icon.async_get_icons(hass, "entity")
    assert icons == {}

    icons = await icon.async_get_icons(hass, "entity_component")
    assert icons == {}

    # Set up test switch component
    assert await async_setup_component(hass, "switch", {"switch": {"platform": "test"}})

    # Test getting icons for the entity component
    icons = await icon.async_get_icons(hass, "entity_component")
    assert icons["switch"]["_"]["default"] == "mdi:toggle-switch-variant"

    # Test services icons are available
    icons = await icon.async_get_icons(hass, "services")
    assert len(icons) == 1
    assert icons["switch"]["turn_off"] == "mdi:toggle-switch-variant-off"

    # Ensure icons file for platform isn't loaded, as that isn't supported
    icons = await icon.async_get_icons(hass, "entity")
    assert icons == {}
    with pytest.raises(ValueError, match="test.switch"):
        await icon.async_get_icons(hass, "entity", ["test.switch"])

    # Load up an custom integration
    hass.config.components.add("test_package")
    await hass.async_block_till_done()

    icons = await icon.async_get_icons(hass, "entity")
    assert len(icons) == 1

    assert icons == {
        "test_package": {
            "switch": {
                "something": {"state": {"away": "mdi:home-outline", "home": "mdi:home"}}
            }
        }
    }

    icons = await icon.async_get_icons(hass, "services")
    assert len(icons) == 2
    assert icons["test_package"]["enable_god_mode"] == "mdi:shield"

    # Load another one
    hass.config.components.add("test_embedded")
    await hass.async_block_till_done()

    icons = await icon.async_get_icons(hass, "entity")
    assert len(icons) == 2

    assert icons["test_package"] == {
        "switch": {
            "something": {"state": {"away": "mdi:home-outline", "home": "mdi:home"}}
        }
    }

    # Test getting non-existing integration
    with pytest.raises(
        IntegrationNotFound, match="Integration 'non_existing' not found"
    ):
        await icon.async_get_icons(hass, "entity", ["non_existing"])


async def test_get_icons_while_loading_components(hass: HomeAssistant) -> None:
    """Test the get icons helper loads icons."""
    integration = Mock(file_path=pathlib.Path(__file__))
    integration.name = "Component 1"
    hass.config.components.add("component1")
    load_count = 0

    def mock_load_icons_files(files):
        """Mock load icon files."""
        nonlocal load_count
        load_count += 1
        return {"component1": {"entity": {"climate": {"test": {"icon": "mdi:home"}}}}}

    with (
        patch(
            "homeassistant.helpers.icon._component_icons_path",
            return_value="choochoo.json",
        ),
        patch(
            "homeassistant.helpers.icon._load_icons_files",
            mock_load_icons_files,
        ),
        patch(
            "homeassistant.helpers.icon.async_get_integrations",
            return_value={"component1": integration},
        ),
    ):
        times = 5
        all_icons = [await icon.async_get_icons(hass, "entity") for _ in range(times)]

    assert all_icons == [
        {"component1": {"climate": {"test": {"icon": "mdi:home"}}}}
        for _ in range(times)
    ]
    assert load_count == 1


async def test_caching(hass: HomeAssistant) -> None:
    """Test we cache data."""
    hass.config.components.add("binary_sensor")
    hass.config.components.add("switch")

    # Patch with same method so we can count invocations
    with patch(
        "homeassistant.helpers.icon.build_resources",
        side_effect=icon.build_resources,
    ) as mock_build:
        load1 = await icon.async_get_icons(hass, "entity_component")
        assert len(mock_build.mock_calls) == 2

        load2 = await icon.async_get_icons(hass, "entity_component")
        assert len(mock_build.mock_calls) == 2

        assert load1 == load2

        assert load1["binary_sensor"]
        assert load1["switch"]

    load_switch_only = await icon.async_get_icons(
        hass, "entity_component", integrations={"switch"}
    )
    assert load_switch_only
    assert list(load_switch_only) == ["switch"]

    load_binary_sensor_only = await icon.async_get_icons(
        hass, "entity_component", integrations={"binary_sensor"}
    )
    assert load_binary_sensor_only
    assert list(load_binary_sensor_only) == ["binary_sensor"]

    # Check if new loaded component, trigger load
    hass.config.components.add("media_player")
    with patch(
        "homeassistant.helpers.icon._load_icons_files",
        side_effect=icon._load_icons_files,
    ) as mock_load:
        load_sensor_only = await icon.async_get_icons(
            hass, "entity_component", integrations={"switch"}
        )
        assert load_sensor_only
        assert len(mock_load.mock_calls) == 0

        await icon.async_get_icons(
            hass, "entity_component", integrations={"media_player"}
        )
        assert len(mock_load.mock_calls) == 1
