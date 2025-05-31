import pytest
from frisquet_connect.const import (
    CLIMATE_TRANSLATIONS_KEY,
    SENSOR_CURRENT_BOILER_DATETIME_TRANSLATIONS_KEY,
    SENSOR_ALARM_TRANSLATIONS_KEY,
    SENSOR_HEATING_CONSUMPTION_TRANSLATIONS_KEY,
    SENSOR_INSIDE_THERMOMETER_TRANSLATIONS_KEY,
    SENSOR_BOILER_LAST_UPDATE_TRANSLATIONS_KEY,
    SENSOR_OUTSIDE_THERMOMETER_TRANSLATIONS_KEY,
    SENSOR_SANITARY_CONSUMPTION_TRANSLATIONS_KEY,
    WATER_HEATER_TRANSLATIONS_KEY,
)
from utils import read_translation_file
from homeassistant.const import Platform


@pytest.mark.asyncio
async def test_async_sanity_check_comparison():
    default_translation = read_translation_file("strings")
    fr_translation = read_translation_file("strings", "fr")

    recursive_check(default_translation, fr_translation)


@pytest.mark.asyncio
async def test_async_sanity_check_missing_key_translations():
    default_translation = read_translation_file("strings")
    sanity_check_missing_key_common(default_translation)


@pytest.mark.asyncio
async def test_async_sanity_check_missing_key_icones():
    default_icons = read_translation_file("icons")
    sanity_check_missing_key_common(default_icons)


def sanity_check_missing_key_common(default_translation: dict):

    default_entities = default_translation.get("entity")
    types = {
        Platform.CLIMATE: [CLIMATE_TRANSLATIONS_KEY],
        Platform.WATER_HEATER: [WATER_HEATER_TRANSLATIONS_KEY],
        Platform.SENSOR: [
            SENSOR_CURRENT_BOILER_DATETIME_TRANSLATIONS_KEY,
            SENSOR_BOILER_LAST_UPDATE_TRANSLATIONS_KEY,
            SENSOR_ALARM_TRANSLATIONS_KEY,
            SENSOR_INSIDE_THERMOMETER_TRANSLATIONS_KEY,
            SENSOR_OUTSIDE_THERMOMETER_TRANSLATIONS_KEY,
            SENSOR_HEATING_CONSUMPTION_TRANSLATIONS_KEY,
            SENSOR_SANITARY_CONSUMPTION_TRANSLATIONS_KEY,
        ],
    }

    # Check if all entities defined the platform are in the translation file
    for platform, translation_keys in types.items():
        for translation_key in translation_keys:
            assert translation_key in default_entities[platform]

    # Check if all entities defined in the translation file are in the dedicated platform
    for platform, platform_entities in default_entities.items():
        for entity in platform_entities.keys():
            assert entity in types[platform]


def recursive_check(default_translation, fr_translation):
    for key in default_translation.keys():
        if isinstance(default_translation[key], dict):
            recursive_check(default_translation[key], fr_translation[key])
        else:
            assert key in fr_translation.keys()
