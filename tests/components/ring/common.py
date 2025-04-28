"""Common methods used across the tests for ring devices."""

from unittest.mock import patch

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.ring import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, translation
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_platform(hass: HomeAssistant, platform: Platform) -> None:
    """Set up the ring platform and prerequisites."""
    if not hass.config_entries.async_has_entries(DOMAIN):
        MockConfigEntry(
            domain=DOMAIN, data={"username": "foo", "token": {}}
        ).add_to_hass(hass)
    with patch("homeassistant.components.ring.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)


async def setup_automation(hass: HomeAssistant, alias: str, entity_id: str) -> None:
    """Set up an automation for tests."""
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: {
                "alias": alias,
                "trigger": {"platform": "state", "entity_id": entity_id, "to": "on"},
                "action": {"action": "notify.notify", "metadata": {}, "data": {}},
            }
        },
    )


async def async_check_entity_translations(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_id: str,
    platform_domain: str,
) -> None:
    """Check that entity translations are used correctly.

    Check no unused translations in strings.
    Check no translation_key defined when translation not in strings.
    Check no translation defined when device class translation can be used.
    """
    entity_entries = er.async_entries_for_config_entry(entity_registry, config_entry_id)

    assert entity_entries
    assert len({entity_entry.domain for entity_entry in entity_entries}) == 1, (
        "Limit the loaded platforms to 1 platform."
    )

    translations = await translation.async_get_translations(
        hass, "en", "entity", [DOMAIN]
    )
    device_class_translations = await translation.async_get_translations(
        hass, "en", "entity_component", [platform_domain]
    )
    unique_device_classes = set()
    used_translation_keys = set()
    for entity_entry in entity_entries:
        dc_translation = None
        if entity_entry.original_device_class:
            dc_translation_key = f"component.{platform_domain}.entity_component.{entity_entry.original_device_class.value}.name"
            dc_translation = device_class_translations.get(dc_translation_key)

        if entity_entry.translation_key:
            key = f"component.{DOMAIN}.entity.{entity_entry.domain}.{entity_entry.translation_key}.name"
            entity_translation = translations.get(key)
            assert entity_translation, (
                f"Translation key {entity_entry.translation_key} defined for {entity_entry.entity_id} not in strings.json"
            )
            assert dc_translation != entity_translation, (
                f"Translation {key} is defined the same as the device class translation."
            )
            used_translation_keys.add(key)

        else:
            unique_key = (entity_entry.device_id, entity_entry.original_device_class)
            assert unique_key not in unique_device_classes, (
                f"No translation key and multiple entities using {entity_entry.original_device_class}"
            )
            unique_device_classes.add(entity_entry.original_device_class)

    for defined_key in translations:
        if defined_key.split(".")[3] != platform_domain:
            continue
        assert defined_key in used_translation_keys, (
            f"Translation key {defined_key} unused."
        )
