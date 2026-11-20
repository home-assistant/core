"""Switcher integration helpers functions."""

import asyncio
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from aioswitcher.api.remotes import SwitcherBreezeRemoteManager
from aioswitcher.bridge import SwitcherBridge
from aioswitcher.device import SwitcherBase

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, singleton
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.start import async_at_started

from .const import DISCOVERY_TIME_SEC, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Version in which deprecated entities will be removed.
DEPRECATED_REMOVAL_VERSION = "2027.6.0"


async def async_discover_devices() -> dict[str, SwitcherBase]:
    """Discover Switcher devices."""
    _LOGGER.debug("Starting discovery")
    discovered_devices = {}

    @callback
    def on_device_data_callback(device: SwitcherBase) -> None:
        """Use as a callback for device data."""
        if device.device_id in discovered_devices:
            return

        discovered_devices[device.device_id] = device

    bridge = SwitcherBridge(on_device_data_callback)
    await bridge.start()
    await asyncio.sleep(DISCOVERY_TIME_SEC)
    await bridge.stop()

    _LOGGER.debug("Finished discovery, discovered devices: %s", len(discovered_devices))
    return discovered_devices


@singleton.singleton("switcher_breeze_remote_manager")
def get_breeze_remote_manager(hass: HomeAssistant) -> SwitcherBreezeRemoteManager:
    """Get Switcher Breeze remote manager."""
    return SwitcherBreezeRemoteManager()


@callback
def deprecate_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    *,
    async_on_unload: Callable[[Callable[[], None]], None],
    platform_domain: str,
    entity_unique_id: str,
    issue_id: str,
    translation_key: str,
) -> bool:
    """Handle deprecation of an entity that has been replaced.

    Return True if the deprecated entity should still be set up, which is the
    case while it exists in the entity registry. A repair issue informs the user
    about the replacement and the removal date; when the entity is still used by
    automations or scripts they are listed in the issue. The entity is removed
    once the user disables it and nothing references it anymore. New
    installations never create the entity.
    """
    if (
        entity_registry.async_get_entity_id(platform_domain, DOMAIN, entity_unique_id)
        is None
    ):
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    # Automations and scripts may not be loaded yet during startup.
    if hass.state is not CoreState.running:

        @callback
        def _async_recheck(_: HomeAssistant) -> None:
            _async_check_deprecated_entity(
                hass,
                entity_registry,
                platform_domain=platform_domain,
                entity_unique_id=entity_unique_id,
                issue_id=issue_id,
                translation_key=translation_key,
            )

        async_on_unload(async_at_started(hass, _async_recheck))
        return True

    return _async_check_deprecated_entity(
        hass,
        entity_registry,
        platform_domain=platform_domain,
        entity_unique_id=entity_unique_id,
        issue_id=issue_id,
        translation_key=translation_key,
    )


@callback
def _async_check_deprecated_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    *,
    platform_domain: str,
    entity_unique_id: str,
    issue_id: str,
    translation_key: str,
) -> bool:
    """Check whether a deprecated entity should remain in the registry."""
    entity_id = entity_registry.async_get_entity_id(
        platform_domain, DOMAIN, entity_unique_id
    )
    if entity_id is None:
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    entity_entry = entity_registry.async_get(entity_id)
    if TYPE_CHECKING:
        assert entity_entry is not None

    items = _automations_and_scripts_using_entity(hass, entity_registry, entity_id)

    if entity_entry.disabled and not items:
        entity_registry.async_remove(entity_id)
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    placeholders = {
        "entity_id": entity_id,
        "entity_name": entity_entry.name or entity_entry.original_name or entity_id,
    }
    if items:
        translation_key = f"{translation_key}_scripts"
        placeholders["items"] = "\n".join(items)

    async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version=DEPRECATED_REMOVAL_VERSION,
        config_entry_id=entity_entry.config_entry_id,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )
    return True


def _automations_and_scripts_using_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> list[str]:
    """Return markdown list items for automations and scripts using an entity."""
    automations = automations_with_entity(hass, entity_id)
    scripts = scripts_with_entity(hass, entity_id)
    if not automations and not scripts:
        return []

    items: list[str] = []
    for integration, used_entities in (
        ("automation", automations),
        ("script", scripts),
    ):
        for used_entity_id in used_entities:
            if entry := entity_registry.async_get(used_entity_id):
                items.append(
                    f"- [{entry.original_name}](/config/{integration}/edit/{entry.unique_id})"
                )
            else:
                items.append(f"- `{used_entity_id}`")

    return items
