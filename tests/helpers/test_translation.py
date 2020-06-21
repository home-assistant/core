"""Test the translation helper."""
import asyncio
from os import path
import pathlib

import pytest

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.generated import config_flows
from homeassistant.helpers import translation
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component, setup_component

from tests.async_mock import Mock, patch


@pytest.fixture
def mock_config_flows():
    """Mock the config flows."""
    flows = []
    with patch.object(config_flows, "FLOWS", flows):
        yield flows


def test_flatten():
    """Test the flatten function."""
    data = {"parent1": {"child1": "data1", "child2": "data2"}, "parent2": "data3"}

    flattened = translation.flatten(data)

    assert flattened == {
        "parent1.child1": "data1",
        "parent1.child2": "data2",
        "parent2": "data3",
    }


async def test_component_translation_path(hass):
    """Test the component translation file function."""
    assert await async_setup_component(
        hass,
        "switch",
        {"switch": [{"platform": "test"}, {"platform": "test_embedded"}]},
    )
    assert await async_setup_component(hass, "test_standalone", {"test_standalone"})
    assert await async_setup_component(hass, "test_package", {"test_package"})

    (
        int_test,
        int_test_embedded,
        int_test_standalone,
        int_test_package,
    ) = await asyncio.gather(
        async_get_integration(hass, "test"),
        async_get_integration(hass, "test_embedded"),
        async_get_integration(hass, "test_standalone"),
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

    assert (
        translation.component_translation_path(
            "test_standalone", "en", int_test_standalone
        )
        is None
    )

    assert path.normpath(
        translation.component_translation_path("test_package", "en", int_test_package)
    ) == path.normpath(
        hass.config.path("custom_components", "test_package", "translations", "en.json")
    )


def test_load_translations_files(hass):
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


async def test_get_translations(hass, mock_config_flows):
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


async def test_get_translations_loads_config_flows(hass, mock_config_flows):
    """Test the get translations helper loads config flow translations."""
    mock_config_flows.append("component1")
    integration = Mock(file_path=pathlib.Path(__file__))
    integration.name = "Component 1"

    with patch(
        "homeassistant.helpers.translation.component_translation_path",
        return_value="bla.json",
    ), patch(
        "homeassistant.helpers.translation.load_translations_files",
        return_value={"component1": {"hello": "world"}},
    ), patch(
        "homeassistant.helpers.translation.async_get_integration",
        return_value=integration,
    ):
        translations = await translation.async_get_translations(
            hass, "en", "hello", config_flow=True
        )

    assert translations == {
        "component.component1.hello": "world",
    }

    assert "component1" not in hass.config.components


async def test_get_translations_while_loading_components(hass):
    """Test the get translations helper loads config flow translations."""
    integration = Mock(file_path=pathlib.Path(__file__))
    integration.name = "Component 1"
    hass.config.components.add("component1")

    def mock_load_translation_files(files):
        """Mock load translation files."""
        # Mimic race condition by loading a component during setup
        setup_component(hass, "persistent_notification", {})
        return {"component1": {"hello": "world"}}

    with patch(
        "homeassistant.helpers.translation.component_translation_path",
        return_value="bla.json",
    ), patch(
        "homeassistant.helpers.translation.load_translations_files",
        mock_load_translation_files,
    ), patch(
        "homeassistant.helpers.translation.async_get_integration",
        return_value=integration,
    ):
        translations = await translation.async_get_translations(hass, "en", "hello")

    assert translations == {
        "component.component1.hello": "world",
    }


async def test_get_translation_categories(hass):
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


async def test_translation_merging(hass, caplog):
    """Test we merge translations of two integrations."""
    hass.config.components.add("sensor.moon")
    hass.config.components.add("sensor.season")
    hass.config.components.add("sensor")

    translations = await translation.async_get_translations(hass, "en", "state")

    assert "component.sensor.state.moon__phase.first_quarter" in translations
    assert "component.sensor.state.season__season.summer" in translations

    # Clear cache
    hass.bus.async_fire(EVENT_COMPONENT_LOADED)
    await hass.async_block_till_done()

    # Patch in some bad translation data

    orig_load_translations = translation.load_translations_files

    def mock_load_translations_files(files):
        """Mock loading."""
        result = orig_load_translations(files)
        result["sensor.season"] = {"state": "bad data"}
        return result

    with patch(
        "homeassistant.helpers.translation.load_translations_files",
        side_effect=mock_load_translations_files,
    ):
        translations = await translation.async_get_translations(hass, "en", "state")

        assert "component.sensor.state.moon__phase.first_quarter" in translations

    assert (
        "An integration providing translations for sensor provided invalid data: bad data"
        in caplog.text
    )


async def test_caching(hass):
    """Test we cache data."""
    hass.config.components.add("sensor")

    # Patch with same method so we can count invocations
    with patch(
        "homeassistant.helpers.translation.merge_resources",
        side_effect=translation.merge_resources,
    ) as mock_merge:
        await translation.async_get_translations(hass, "en", "state")
        assert len(mock_merge.mock_calls) == 1

        await translation.async_get_translations(hass, "en", "state")
        assert len(mock_merge.mock_calls) == 1

        # This event clears the cache so we should record another call
        hass.bus.async_fire(EVENT_COMPONENT_LOADED)
        await hass.async_block_till_done()

        await translation.async_get_translations(hass, "en", "state")
        assert len(mock_merge.mock_calls) == 2


async def test_custom_component_translations(hass):
    """Test getting translation from custom components."""
    hass.config.components.add("test_standalone")
    hass.config.components.add("test_embedded")
    hass.config.components.add("test_package")
    assert await translation.async_get_translations(hass, "en", "state") == {}
