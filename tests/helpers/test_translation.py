"""Test the translation helper."""

import asyncio
from os import path
import pathlib
from typing import Any
from unittest.mock import Mock, call, patch

import pytest

from homeassistant import loader
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def _disable_translations_once(disable_translations_once):
    """Override loading translations once."""


@pytest.fixture
def mock_config_flows():
    """Mock the config flows."""
    flows = {"integration": [], "helper": {}}
    with patch.object(loader, "FLOWS", flows):
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
    assert await async_setup_component(hass, "test_package", {"test_package": None})
    int_test_package = await async_get_integration(hass, "test_package")

    assert path.normpath(
        translation.component_translation_path("en", int_test_package)
    ) == path.normpath(
        hass.config.path("custom_components", "test_package", "translations", "en.json")
    )


def test_load_translations_files_by_language(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the load translation files function."""
    # Test one valid and one invalid file
    en_file = hass.config.path("custom_components", "test", "translations", "en.json")
    invalid_file = hass.config.path(
        "custom_components", "test", "translations", "invalid.json"
    )
    broken_file = hass.config.path(
        "custom_components", "test", "translations", "_broken.json"
    )
    assert translation._load_translations_files_by_language(
        {
            "en": {"test": en_file},
            "invalid": {"test": invalid_file},
            "broken": {"test": broken_file},
        }
    ) == {
        "broken": {},
        "en": {
            "test": {
                "entity": {
                    "switch": {
                        "other1": {"name": "Other 1"},
                        "other2": {"name": "Other 2"},
                        "other3": {"name": "Other 3"},
                        "other4": {"name": "Other 4"},
                        "outlet": {"name": "Outlet " "{placeholder}"},
                    }
                },
                "something": "else",
            }
        },
        "invalid": {"test": {}},
    }
    assert "Translation file is unexpected type" in caplog.text
    assert "_broken.json" in caplog.text


@pytest.mark.parametrize(
    ("language", "expected_translation", "expected_errors"),
    [
        (
            "en",
            {
                "component.test.entity.switch.other1.name": "Other 1",
                "component.test.entity.switch.other2.name": "Other 2",
                "component.test.entity.switch.other3.name": "Other 3",
                "component.test.entity.switch.other4.name": "Other 4",
                "component.test.entity.switch.outlet.name": "Outlet {placeholder}",
            },
            [],
        ),
        (
            "es",
            {
                "component.test.entity.switch.other1.name": "Otra 1",
                "component.test.entity.switch.other2.name": "Otra 2",
                "component.test.entity.switch.other3.name": "Otra 3",
                "component.test.entity.switch.other4.name": "Otra 4",
                "component.test.entity.switch.outlet.name": "Enchufe {placeholder}",
            },
            [],
        ),
        (
            "de",
            {
                # Correct
                "component.test.entity.switch.other1.name": "Anderes 1",
                # Translation has placeholder missing in English
                "component.test.entity.switch.other2.name": "Other 2",
                # Correct (empty translation)
                "component.test.entity.switch.other3.name": "",
                # Translation missing
                "component.test.entity.switch.other4.name": "Other 4",
                # Mismatch in placeholders
                "component.test.entity.switch.outlet.name": "Outlet {placeholder}",
            },
            [
                "component.test.entity.switch.other2.name",
                "component.test.entity.switch.outlet.name",
            ],
        ),
    ],
)
async def test_load_translations_files_invalid_localized_placeholders(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
    language: str,
    expected_translation: dict,
    expected_errors: bool,
) -> None:
    """Test the load translation files with invalid localized placeholders."""
    caplog.clear()
    translations = await translation.async_get_translations(
        hass, language, "entity", ["test"]
    )
    assert translations == expected_translation

    assert ("Validation of translation placeholders" in caplog.text) == (
        len(expected_errors) > 0
    )
    for expected_error in expected_errors:
        assert (
            f"Validation of translation placeholders for localized ({language}) string {expected_error} failed"
            in caplog.text
        )


async def test_get_translations(
    hass: HomeAssistant, mock_config_flows, enable_custom_integrations: None
) -> None:
    """Test the get translations helper."""
    translations = await translation.async_get_translations(hass, "en", "entity")
    assert translations == {}

    assert await async_setup_component(hass, "switch", {"switch": {"platform": "test"}})
    await hass.async_block_till_done()

    translations = await translation.async_get_translations(
        hass, "en", "entity", {"test"}
    )

    assert translations == {
        "component.test.entity.switch.other1.name": "Other 1",
        "component.test.entity.switch.other2.name": "Other 2",
        "component.test.entity.switch.other3.name": "Other 3",
        "component.test.entity.switch.other4.name": "Other 4",
        "component.test.entity.switch.outlet.name": "Outlet {placeholder}",
    }

    translations = await translation.async_get_translations(
        hass, "de", "entity", {"test"}
    )

    assert translations == {
        "component.test.entity.switch.other1.name": "Anderes 1",
        "component.test.entity.switch.other2.name": "Other 2",
        "component.test.entity.switch.other3.name": "",
        "component.test.entity.switch.other4.name": "Other 4",
        "component.test.entity.switch.outlet.name": "Outlet {placeholder}",
    }

    # Test a partial translation
    translations = await translation.async_get_translations(
        hass, "es", "entity", {"test"}
    )

    assert translations == {
        "component.test.entity.switch.other1.name": "Otra 1",
        "component.test.entity.switch.other2.name": "Otra 2",
        "component.test.entity.switch.other3.name": "Otra 3",
        "component.test.entity.switch.other4.name": "Otra 4",
        "component.test.entity.switch.outlet.name": "Enchufe {placeholder}",
    }

    # Test that an untranslated language falls back to English.
    translations = await translation.async_get_translations(
        hass, "invalid-language", "entity", {"test"}
    )

    assert translations == {
        "component.test.entity.switch.other1.name": "Other 1",
        "component.test.entity.switch.other2.name": "Other 2",
        "component.test.entity.switch.other3.name": "Other 3",
        "component.test.entity.switch.other4.name": "Other 4",
        "component.test.entity.switch.outlet.name": "Outlet {placeholder}",
    }


async def test_get_translations_loads_config_flows(
    hass: HomeAssistant, mock_config_flows
) -> None:
    """Test the get translations helper loads config flow translations."""
    mock_config_flows["integration"].append("component1")
    integration = Mock(file_path=pathlib.Path(__file__))
    integration.name = "Component 1"

    with (
        patch(
            "homeassistant.helpers.translation.component_translation_path",
            return_value="bla.json",
        ),
        patch(
            "homeassistant.helpers.translation._load_translations_files_by_language",
            return_value={"en": {"component1": {"title": "world"}}},
        ),
        patch(
            "homeassistant.helpers.translation.async_get_integrations",
            return_value={"component1": integration},
        ),
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

    with (
        patch(
            "homeassistant.helpers.translation.component_translation_path",
            return_value="bla.json",
        ),
        patch(
            "homeassistant.helpers.translation._load_translations_files_by_language",
            return_value={"en": {"component2": {"title": "world"}}},
        ),
        patch(
            "homeassistant.helpers.translation.async_get_integrations",
            return_value={"component2": integration},
        ),
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

    def mock_load_translation_files(
        files: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Mock load translation files."""
        nonlocal load_count
        load_count += 1
        # Mimic race condition by loading a component during setup

        return {language: {"component1": {"title": "world"}} for language in files}

    with (
        patch(
            "homeassistant.helpers.translation.component_translation_path",
            return_value="bla.json",
        ),
        patch(
            "homeassistant.helpers.translation._load_translations_files_by_language",
            mock_load_translation_files,
        ),
        patch(
            "homeassistant.helpers.translation.async_get_integrations",
            return_value={"component1": integration},
        ),
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


async def test_ensure_translations_still_load_if_one_integration_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that if one integration fails to load we can still get translations."""
    hass.config.components.add("sensor")
    hass.config.components.add("broken")

    sensor_integration = await loader.async_get_integration(hass, "sensor")

    with patch(
        "homeassistant.helpers.translation.async_get_integrations",
        return_value={
            "sensor": sensor_integration,
            "broken": Exception("unhandled failure"),
        },
    ):
        translations = await translation.async_get_translations(
            hass, "en", "entity_component", integrations={"sensor", "broken"}
        )
        assert "Failed to load integration for translation" in caplog.text
        assert "broken" in caplog.text

    assert translations

    sensor_translations = await translation.async_get_translations(
        hass, "en", "entity_component", integrations={"sensor"}
    )

    assert translations == sensor_translations


async def test_load_translations_all_integrations_broken(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure we do not try to load translations again if the integration is broken."""
    hass.config.components.add("broken")
    hass.config.components.add("broken2")

    with patch(
        "homeassistant.helpers.translation.async_get_integrations",
        return_value={
            "broken2": Exception("unhandled failure"),
            "broken": Exception("unhandled failure"),
        },
    ):
        translations = await translation.async_get_translations(
            hass, "en", "entity_component", integrations={"broken", "broken2"}
        )
    assert "Failed to load integration for translation" in caplog.text
    assert "broken" in caplog.text
    assert "broken2" in caplog.text
    assert not translations
    caplog.clear()

    translations = await translation.async_get_translations(
        hass, "en", "entity_component", integrations={"broken", "broken2"}
    )
    assert not translations
    # Ensure we do not try again
    assert "Failed to load integration for translation" not in caplog.text


async def test_caching(hass: HomeAssistant) -> None:
    """Test we cache data."""
    hass.config.components.add("sensor")
    hass.config.components.add("light")

    # Patch with same method so we can count invocations
    with patch(
        "homeassistant.helpers.translation.build_resources",
        side_effect=translation.build_resources,
    ) as mock_build_resources:
        load1 = await translation.async_get_translations(hass, "en", "entity_component")
        assert len(mock_build_resources.mock_calls) == 5

        load2 = await translation.async_get_translations(hass, "en", "entity_component")
        assert len(mock_build_resources.mock_calls) == 5

        assert load1 == load2

        for key in load1:
            assert key.startswith(
                (
                    "component.sensor.entity_component.",
                    "component.light.entity_component.",
                )
            )

    load_sensor_only = await translation.async_get_translations(
        hass, "en", "entity_component", integrations={"sensor"}
    )
    assert load_sensor_only
    for key in load_sensor_only:
        assert key.startswith("component.sensor.entity_component.")

    load_light_only = await translation.async_get_translations(
        hass, "en", "entity_component", integrations={"light"}
    )
    assert load_light_only
    for key in load_light_only:
        assert key.startswith("component.light.entity_component.")

    hass.config.components.add("media_player")

    # Patch with same method so we can count invocations
    with patch(
        "homeassistant.helpers.translation.build_resources",
        side_effect=translation.build_resources,
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


async def test_get_cached_translations(
    hass: HomeAssistant, mock_config_flows, enable_custom_integrations: None
) -> None:
    """Test the get cached translations helper."""
    translations = await translation.async_get_translations(hass, "en", "entity")
    assert translations == {}

    assert await async_setup_component(hass, "switch", {"switch": {"platform": "test"}})
    await hass.async_block_till_done()

    await translation._async_get_translations_cache(hass).async_load("en", {"test"})

    translations = translation.async_get_cached_translations(
        hass, "en", "entity", "test"
    )
    assert translations == {
        "component.test.entity.switch.other1.name": "Other 1",
        "component.test.entity.switch.other2.name": "Other 2",
        "component.test.entity.switch.other3.name": "Other 3",
        "component.test.entity.switch.other4.name": "Other 4",
        "component.test.entity.switch.outlet.name": "Outlet {placeholder}",
    }

    await translation._async_get_translations_cache(hass).async_load("es", {"test"})

    # Test a partial translation
    translations = translation.async_get_cached_translations(
        hass, "es", "entity", "test"
    )

    assert translations == {
        "component.test.entity.switch.other1.name": "Otra 1",
        "component.test.entity.switch.other2.name": "Otra 2",
        "component.test.entity.switch.other3.name": "Otra 3",
        "component.test.entity.switch.other4.name": "Otra 4",
        "component.test.entity.switch.outlet.name": "Enchufe {placeholder}",
    }

    await translation._async_get_translations_cache(hass).async_load(
        "invalid-language", {"test"}
    )

    # Test that an untranslated language falls back to English.
    translations = translation.async_get_cached_translations(
        hass, "invalid-language", "entity", "test"
    )

    assert translations == {
        "component.test.entity.switch.other1.name": "Other 1",
        "component.test.entity.switch.other2.name": "Other 2",
        "component.test.entity.switch.other3.name": "Other 3",
        "component.test.entity.switch.other4.name": "Other 4",
        "component.test.entity.switch.outlet.name": "Outlet {placeholder}",
    }


async def test_setup(hass: HomeAssistant):
    """Test the setup load listeners helper."""
    translation.async_setup(hass)

    # Should not be called if the language is the current language
    with patch(
        "homeassistant.helpers.translation._TranslationCache.async_load",
    ) as mock:
        hass.bus.async_fire(EVENT_CORE_CONFIG_UPDATE, {"language": "en"})
        await hass.async_block_till_done()
        mock.assert_not_called()

    # Should be called if the language is different
    with patch(
        "homeassistant.helpers.translation._TranslationCache.async_load",
    ) as mock:
        hass.bus.async_fire(EVENT_CORE_CONFIG_UPDATE, {"language": "es"})
        await hass.async_block_till_done()
        mock.assert_called_once_with("es", set())

    with patch(
        "homeassistant.helpers.translation._TranslationCache.async_load",
    ) as mock:
        hass.bus.async_fire(EVENT_CORE_CONFIG_UPDATE, {})
        await hass.async_block_till_done()
        mock.assert_not_called()


async def test_translate_state(hass: HomeAssistant):
    """Test the state translation helper."""
    result = translation.async_translate_state(
        hass, "unavailable", "binary_sensor", "platform", "translation_key", None
    )
    assert result == "unavailable"

    result = translation.async_translate_state(
        hass, "unknown", "binary_sensor", "platform", "translation_key", None
    )
    assert result == "unknown"

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value={
            "component.platform.entity.binary_sensor.translation_key.state.on": "TRANSLATED"
        },
    ) as mock:
        result = translation.async_translate_state(
            hass, "on", "binary_sensor", "platform", "translation_key", None
        )
        mock.assert_called_once_with(hass, hass.config.language, "entity")
        assert result == "TRANSLATED"

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value={
            "component.binary_sensor.entity_component.device_class.state.on": "TRANSLATED"
        },
    ) as mock:
        result = translation.async_translate_state(
            hass, "on", "binary_sensor", "platform", None, "device_class"
        )
        mock.assert_called_once_with(hass, hass.config.language, "entity_component")
        assert result == "TRANSLATED"

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value={
            "component.binary_sensor.entity_component._.state.on": "TRANSLATED"
        },
    ) as mock:
        result = translation.async_translate_state(
            hass, "on", "binary_sensor", "platform", None, None
        )
        mock.assert_called_once_with(hass, hass.config.language, "entity_component")
        assert result == "TRANSLATED"

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value={},
    ) as mock:
        result = translation.async_translate_state(
            hass, "on", "binary_sensor", "platform", None, None
        )
        mock.assert_has_calls(
            [
                call(hass, hass.config.language, "entity_component"),
            ]
        )
        assert result == "on"

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value={},
    ) as mock:
        result = translation.async_translate_state(
            hass, "on", "binary_sensor", "platform", "translation_key", "device_class"
        )
        mock.assert_has_calls(
            [
                call(hass, hass.config.language, "entity"),
                call(hass, hass.config.language, "entity_component"),
            ]
        )
        assert result == "on"


async def test_get_translations_still_has_title_without_translations_files(
    hass: HomeAssistant, mock_config_flows
) -> None:
    """Test the title still gets added in if there are no translation files."""
    mock_config_flows["integration"].append("component1")
    integration = Mock(file_path=pathlib.Path(__file__))
    integration.name = "Component 1"

    with (
        patch(
            "homeassistant.helpers.translation.component_translation_path",
            return_value="bla.json",
        ),
        patch(
            "homeassistant.helpers.translation._load_translations_files_by_language",
            return_value={},
        ),
        patch(
            "homeassistant.helpers.translation.async_get_integrations",
            return_value={"component1": integration},
        ),
    ):
        translations = await translation.async_get_translations(
            hass, "en", "title", config_flow=True
        )
        translations_again = await translation.async_get_translations(
            hass, "en", "title", config_flow=True
        )

        assert translations == translations_again

    assert translations == {
        "component.component1.title": "Component 1",
    }
