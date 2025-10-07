"""Ensure quirks are correctly aligned with Home Assistant."""

from __future__ import annotations

from enum import StrEnum

import pytest

from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.tuya.xternal_tuya_device_quirks import (
    register_tuya_quirks,
)
from homeassistant.components.tuya.xternal_tuya_quirks import (
    TUYA_QUIRKS_REGISTRY,
    QuirksRegistry,
    TuyaDeviceQuirk,
)
from homeassistant.components.tuya.xternal_tuya_quirks.device_quirk import (
    BaseTuyaDefinition,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation
from homeassistant.util.json import load_json


@pytest.fixture(scope="module")
def filled_quirks_registry() -> QuirksRegistry:
    """Mock an old config entry that can be migrated."""
    register_tuya_quirks()
    return TUYA_QUIRKS_REGISTRY


_PLATFORM_DEVICE_CLASS: dict[Platform, type[StrEnum]] = {
    Platform.COVER: CoverDeviceClass,
    Platform.SENSOR: SensorDeviceClass,
}


def _validate_quirk_platform(
    quirk: TuyaDeviceQuirk, strings: dict[str, str], platform: str
) -> None:
    """Validate entity translations exist in strings.json."""
    definitions: list[BaseTuyaDefinition] = getattr(quirk, f"{platform}_definitions")
    for definition in definitions:
        # Validate entity translations exist in strings.json.
        full_key = f"entity.{platform}.{definition.translation_key}.name"
        assert definition.translation_string == strings.get(full_key), (
            f"Incorrect or missing translation string for {full_key} in "
            "homeassistant/components/tuya/strings.json"
        )
        # Validate entity state translations exist in strings.json.
        if state_translations := definition.state_translations:
            for state, state_translation in state_translations.items():
                full_key = (
                    f"entity.{platform}.{definition.translation_key}.state.{state}"
                )
                assert state_translation == strings.get(full_key), (
                    f"Incorrect or missing translation string for {full_key} in "
                    "homeassistant/components/tuya/strings.json"
                )
        # Validate device class is valid for platform.
        if definition.device_class is not None:
            device_class_enum = _PLATFORM_DEVICE_CLASS[platform]
            assert definition.device_class in device_class_enum.__members__.values(), (
                f"Invalid quirk device class {definition.device_class} for "
                f"{definition.key} {platform} in {quirk.quirk_file} {quirk.quirk_file_line}"
            )
        # Validate entity category is valid for platform.
        if definition.entity_category is not None:
            assert definition.entity_category in EntityCategory.__members__.values(), (
                f"Invalid quirk entity category {definition.entity_category} for "
                f"{definition.key} {platform} in {quirk.quirk_file} {quirk.quirk_file_line}"
            )


async def test_quirks_validation(
    hass: HomeAssistant, filled_quirks_registry: QuirksRegistry
) -> None:
    """Test that quirks are valid.

    - ensures that all translation strings exist in strings.json
    - ensures that all device classes are valid for the platform
    - ensures that all entity categories are valid for the platform
    """
    json_strings = await hass.async_add_executor_job(
        load_json, "homeassistant/components/tuya/strings.json"
    )
    strings = translation.recursive_flatten("", json_strings)

    for category_devices in filled_quirks_registry._quirks.values():
        for quirk in category_devices.values():
            _validate_quirk_platform(quirk, strings, Platform.COVER)
            _validate_quirk_platform(quirk, strings, Platform.SELECT)
            _validate_quirk_platform(quirk, strings, Platform.SENSOR)
