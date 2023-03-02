"""Test the translation helper."""
import asyncio
from os import path
import pathlib
from unittest.mock import Mock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.generated import config_flows
from homeassistant.helpers import translation
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_config_flows():
    """Mock the config flows."""
    flows = {"integration": [], "helper": {}}
    with patch.object(config_flows, "FLOWS", flows):
        yield flows


def test_recursive_flatten() -> None:
    """Test the flatten function."""
    data = {"parent1": {"child1": "data1", "child2": "data2"}, "parent2": "data3"}

    flattened = translation.recursive_flatten("prefix.", data)

    assert flattened == {
        "prefix.parent1.child1": "data1",
        "prefix.parent1.child2": "data2",
        "prefix.parent2": "data3",
    }


async def test_component_translation_path(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the component translation file function."""
    assert await async_setup_component(
        hass,
        "switch",
        {"switch": [{"platform": "test"}, {"platform": "test_embedded"}]},
    )
    assert await async_setup_component(hass, "test_package", {"test_package"})

    (
        int_test,
        int_test_embedded,
        int_test_package,
    ) = await asyncio.gather(
        async_get_integration(hass, "test"),
        async_get_integration(hass, "test_embedded"),
        async_get_integration(hass, "test_package"),
    )

    assert path.normpath(
        translation.component_translation_path("switch.test", "en", int_test)
    ) == path.normpath(
        hass.config.path("custom_components", "test", "translations", "switch.en.json")
    )

    assert path.normpath(
        translation.component_translation_path(
            "switch.test_embedded", "en", int_test_embedded
        )
    ) == path.normpath(
        hass.config.path(
            "custom_components", "test_embedded", "translations", "switch.en.json"
        )
    )

    assert path.normpath(
        translation.component_translation_path("test_package", "en", int_test_package)
    ) == path.normpath(
        hass.config.path("custom_components", "test_package", "translations", "en.json")
    )


def test_load_translations_files(hass: HomeAssistant) -> None:
    """Test the load translation files function."""
    # Test one valid and one invalid file
    file1 = hass.config.path(
        "custom_components", "test", "translations", "switch.en.json"
    )
    file2 = hass.config.path(
        "custom_components", "test", "translations", "invalid.json"
    )
    assert translation.load_translations_files(
        {"switch.test": file1, "invalid": file2}
    ) == {
        "switch.test": {
            "state": {"string1": "Value 1", "string2": "Value 2"},
            "something": "else",
        },
        "invalid": {},
    }


async def test_get_translations(
    hass: HomeAssistant, mock_config_flows, enable_custom_integrations: None
) -> None:
    """Test the get translations helper."""
    translations = await translation.async_get_translations(hass, "en", "state")
    assert translations == {}

    assert await async_setup_component(hass, "switch", {"switch": {"platform": "test"}})
    await hass.async_block_till_done()

    translations = await translation.async_get_translations(hass, "en", "state")

    assert translations["component.switch.state.string1"] == "Value 1"
    assert translations["component.switch.state.string2"] == "Value 2"

    translations = await translation.async_get_translations(hass, "de", "state")
    assert "component.switch.something" not in translations
    assert translations["component.switch.state.string1"] == "German Value 1"
    assert translations["component.switch.state.string2"] == "German Value 2"

    # Test a partial translation
    translations = await translation.async_get_translations(hass, "es", "state")
    assert translations["component.switch.state.string1"] == "Spanish Value 1"
    assert translations["component.switch.state.string2"] == "Value 2"

    # Test that an untranslated language falls back to English.
    translations = await translation.async_get_translations(
        hass, "invalid-language", "state"
    )
    assert translations["component.switch.state.string1"] == "Value 1"
    assert translations["component.switch.state.string2"] == "Value 2"


async def test_get_translations_loads_config_flows(
    hass: HomeAssistant, mock_config_flows
) -> None:
    """Test the get translations helper loads config flow translations."""
    mock_config_flows["integration"].append("component1")
    integration = Mock(file_path=pathlib.Path(__file__))
    integration.name = "Component 1"

    with patch(
        "homeassistant.helpers.translation.component_translation_path",
        return_value="bla.json",
    ), patch(
        "homeassistant.helpers.translation.load_translations_files",
        return_value={"component1": {"title": "world"}},
    ), patch(
        "homeassistant.helpers.translation.async_get_integrations",
        return_value={"component1": integration},
    ):
        translations = await translation.async_get_translations(
            hass, "en", "title", config_flow=True
        )
        translations_again = await translation.async_get_translations(
            hass, "en", "title", config_flow=True
        )

        assert translations == translations_again

    assert translations == {
        "component.component1.title": "world",
    }

    assert "component1" not in hass.config.components

    mock_config_flows["integration"].append("component2")
    integration = Mock(file_path=pathlib.Path(__file__))
    integration.name = "Component 2"

    with patch(
        "homeassistant.helpers.translation.component_translation_path",
        return_value="bla.json",
    ), patch(
        "homeassistant.helpers.translation.load_translations_files",
        return_value={"component2": {"title": "world"}},
    ), patch(
        "homeassistant.helpers.translation.async_get_integrations",
        return_value={"component2": integration},
    ):
        translations = await translation.async_get_translations(
            hass, "en", "title", config_flow=True
        )
        translations_again = await translation.async_get_translations(
            hass, "en", "title", config_flow=True
        )

        assert translations == translations_again

    assert translations == {
        "component.component1.title": "world",
        "component.component2.title": "world",
    }

    translations_all_cached = await translation.async_get_translations(
        hass, "en", "title", config_flow=True
    )
    assert translations == translations_all_cached

    assert "component1" not in hass.config.components
    assert "component2" not in hass.config.components


async def test_get_translations_while_loading_components(hass: HomeAssistant) -> None:
    """Test the get translations helper loads config flow translations."""
    integration = Mock(file_path=pathlib.Path(__file__))
    integration.name = "Component 1"
    hass.config.components.add("component1")
    load_count = 0

    def mock_load_translation_files(files):
        """Mock load translation files."""
        nonlocal load_count
        load_count += 1
        # Mimic race condition by loading a component during setup

        return {"component1": {"title": "world"}}

    with patch(
        "homeassistant.helpers.translation.component_translation_path",
        return_value="bla.json",
    ), patch(
        "homeassistant.helpers.translation.load_translations_files",
        mock_load_translation_files,
    ), patch(
        "homeassistant.helpers.translation.async_get_integrations",
        return_value={"component1": integration},
    ):
        tasks = [
            translation.async_get_translations(hass, "en", "title") for _ in range(5)
        ]
        all_translations = await asyncio.gather(*tasks)

    assert all_translations[0] == {
        "component.component1.title": "world",
    }
    assert load_count == 1


async def test_get_translation_categories(hass: HomeAssistant) -> None:
    """Test the get translations helper loads config flow translations."""
    with patch.object(translation, "async_get_config_flows", return_value={"light"}):
        translations = await translation.async_get_translations(
            hass, "en", "title", None, True
        )
        assert "component.light.title" in translations

        translations = await translation.async_get_translations(
            hass, "en", "device_automation", None, True
        )
        assert "component.light.device_automation.action_type.turn_on" in translations


async def test_translation_merging(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we merge translations of two integrations."""
    hass.config.components.add("sensor.moon")
    hass.config.components.add("sensor")

    orig_load_translations = translation.load_translations_files

    def mock_load_translations_files(files):
        """Mock loading."""
        result = orig_load_translations(files)
        result["sensor.moon"] = {
            "state": {"moon__phase": {"first_quarter": "First Quarter"}}
        }
        return result

    with patch(
        "homeassistant.helpers.translation.load_translations_files",
        side_effect=mock_load_translations_files,
    ):
        translations = await translation.async_get_translations(hass, "en", "state")

    assert "component.sensor.state.moon__phase.first_quarter" in translations

    hass.config.components.add("sensor.season")

    # Patch in some bad translation data
    def mock_load_bad_translations_files(files):
        """Mock loading."""
        result = orig_load_translations(files)
        result["sensor.season"] = {"state": "bad data"}
        return result

    with patch(
        "homeassistant.helpers.translation.load_translations_files",
        side_effect=mock_load_bad_translations_files,
    ):
        translations = await translation.async_get_translations(hass, "en", "state")

        assert "component.sensor.state.moon__phase.first_quarter" in translations

    assert (
        "An integration providing translations for sensor provided invalid data:"
        " bad data"
    ) in caplog.text


async def test_translation_merging_loaded_apart(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we merge translations of two integrations when they are not loaded at the same time."""
    orig_load_translations = translation.load_translations_files

    def mock_load_translations_files(files):
        """Mock loading."""
        result = orig_load_translations(files)
        result["sensor.moon"] = {
            "state": {"moon__phase": {"first_quarter": "First Quarter"}}
        }
        return result

    hass.config.components.add("sensor")

    with patch(
        "homeassistant.helpers.translation.load_translations_files",
        side_effect=mock_load_translations_files,
    ):
        translations = await translation.async_get_translations(hass, "en", "state")

    assert "component.sensor.state.moon__phase.first_quarter" not in translations

    hass.config.components.add("sensor.moon")

    with patch(
        "homeassistant.helpers.translation.load_translations_files",
        side_effect=mock_load_translations_files,
    ):
        translations = await translation.async_get_translations(hass, "en", "state")

    assert "component.sensor.state.moon__phase.first_quarter" in translations

    with patch(
        "homeassistant.helpers.translation.load_translations_files",
        side_effect=mock_load_translations_files,
    ):
        translations = await translation.async_get_translations(
            hass, "en", "state", integrations={"sensor"}
        )

    assert "component.sensor.state.moon__phase.first_quarter" in translations


async def test_translation_merging_loaded_together(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we merge translations of two integrations when they are loaded at the same time."""
    hass.config.components.add("hue")
    hass.config.components.add("homekit")
    hue_translations = await translation.async_get_translations(
        hass, "en", "config", integrations={"hue"}
    )
    homekit_translations = await translation.async_get_translations(
        hass, "en", "config", integrations={"homekit"}
    )

    translations = await translation.async_get_translations(
        hass, "en", "config", integrations={"hue", "homekit"}
    )
    assert translations == hue_translations | homekit_translations


async def test_caching(hass: HomeAssistant) -> None:
    """Test we cache data."""
    hass.config.components.add("sensor")
    hass.config.components.add("light")

    # Patch with same method so we can count invocations
    with patch(
        "homeassistant.helpers.translation._merge_resources",
        side_effect=translation._merge_resources,
    ) as mock_merge:
        load1 = await translation.async_get_translations(hass, "en", "state")
        assert len(mock_merge.mock_calls) == 1

        load2 = await translation.async_get_translations(hass, "en", "state")
        assert len(mock_merge.mock_calls) == 1

        assert load1 == load2

        for key in load1:
            assert key.startswith("component.sensor.state.") or key.startswith(
                "component.light.state."
            )

    load_sensor_only = await translation.async_get_translations(
        hass, "en", "state", integrations={"sensor"}
    )
    assert load_sensor_only
    for key in load_sensor_only:
        assert key.startswith("component.sensor.state.")

    load_light_only = await translation.async_get_translations(
        hass, "en", "state", integrations={"light"}
    )
    assert load_light_only
    for key in load_light_only:
        assert key.startswith("component.light.state.")

    hass.config.components.add("media_player")

    # Patch with same method so we can count invocations
    with patch(
        "homeassistant.helpers.translation._build_resources",
        side_effect=translation._build_resources,
    ) as mock_build:
        load_sensor_only = await translation.async_get_translations(
            hass, "en", "title", integrations={"sensor"}
        )
        assert load_sensor_only
        for key in load_sensor_only:
            assert key == "component.sensor.title"
        assert len(mock_build.mock_calls) == 0

        assert await translation.async_get_translations(
            hass, "en", "title", integrations={"sensor"}
        )
        assert len(mock_build.mock_calls) == 0

        load_light_only = await translation.async_get_translations(
            hass, "en", "title", integrations={"media_player"}
        )
        assert load_light_only
        for key in load_light_only:
            assert key == "component.media_player.title"
        assert len(mock_build.mock_calls) > 1


async def test_custom_component_translations(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test getting translation from custom components."""
    hass.config.components.add("test_embedded")
    hass.config.components.add("test_package")
    assert await translation.async_get_translations(hass, "en", "state") == {}
