"""Test the translation helper."""
# pylint: disable=protected-access
from os import path
from unittest.mock import patch

import pytest

from homeassistant import config_entries
import homeassistant.helpers.translation as translation
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_config_flows():
    """Mock the config flows."""
    flows = []
    with patch.object(config_entries, 'FLOWS', flows):
        yield flows


def test_flatten():
    """Test the flatten function."""
    data = {
        "parent1": {
            "child1": "data1",
            "child2": "data2",
        },
        "parent2": "data3",
    }

    flattened = translation.flatten(data)

    assert flattened == {
        "parent1.child1": "data1",
        "parent1.child2": "data2",
        "parent2": "data3",
    }


async def test_component_translation_file(hass):
    """Test the component translation file function."""
    assert await async_setup_component(hass, 'switch', {
        'switch': {'platform': 'test'}
    })
    assert await async_setup_component(hass, 'test_standalone', {
        'test_standalone'
    })
    assert await async_setup_component(hass, 'test_package', {
        'test_package'
    })

    assert path.normpath(translation.component_translation_file(
        'switch.test', 'en')) == path.normpath(hass.config.path(
            'custom_components', 'switch', '.translations', 'test.en.json'))

    assert path.normpath(translation.component_translation_file(
        'test_standalone', 'en')) == path.normpath(hass.config.path(
            'custom_components', '.translations', 'test_standalone.en.json'))

    assert path.normpath(translation.component_translation_file(
        'test_package', 'en')) == path.normpath(hass.config.path(
            'custom_components', 'test_package', '.translations', 'en.json'))


def test_load_translations_files(hass):
    """Test the load translation files function."""
    # Test one valid and one invalid file
    file1 = hass.config.path(
        'custom_components', 'switch', '.translations', 'test.en.json')
    file2 = hass.config.path(
        'custom_components', 'switch', '.translations', 'invalid.json')
    assert translation.load_translations_files({
        'switch.test': file1,
        'invalid': file2
    }) == {
        'switch.test': {
            'state': {
                'string1': 'Value 1',
                'string2': 'Value 2',
            }
        },
        'invalid': {},
    }


async def test_get_translations(hass, mock_config_flows):
    """Test the get translations helper."""
    translations = await translation.async_get_translations(hass, 'en')
    assert translations == {}

    assert await async_setup_component(hass, 'switch', {
        'switch': {'platform': 'test'}
    })

    translations = await translation.async_get_translations(hass, 'en')
    assert translations == {
        'component.switch.state.string1': 'Value 1',
        'component.switch.state.string2': 'Value 2',
    }

    translations = await translation.async_get_translations(hass, 'de')
    assert translations == {
        'component.switch.state.string1': 'German Value 1',
        'component.switch.state.string2': 'German Value 2',
    }

    # Test a partial translation
    translations = await translation.async_get_translations(hass, 'es')
    assert translations == {
        'component.switch.state.string1': 'Spanish Value 1',
        'component.switch.state.string2': 'Value 2',
    }

    # Test that an untranslated language falls back to English.
    translations = await translation.async_get_translations(
        hass, 'invalid-language')
    assert translations == {
        'component.switch.state.string1': 'Value 1',
        'component.switch.state.string2': 'Value 2',
    }


async def test_get_translations_loads_config_flows(hass, mock_config_flows):
    """Test the get translations helper loads config flow translations."""
    mock_config_flows.append('component1')

    with patch.object(translation, 'component_translation_file',
                      return_value='bla.json'), \
            patch.object(translation, 'load_translations_files', return_value={
                'component1': {'hello': 'world'}}):
        translations = await translation.async_get_translations(hass, 'en')
    assert translations == {
        'component.component1.hello': 'world'
    }
