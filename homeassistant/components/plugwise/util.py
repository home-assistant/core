"""Utilities for Plugwise."""

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate

from plugwise.exceptions import PlugwiseException

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.typing import NoEventData
from homeassistant.setup import ATTR_COMPONENT, EventComponentLoaded

from .const import DOMAIN
from .entity import PlugwiseEntity

# Version in which deprecated entities will be removed.
DEPRECATED_REMOVAL_VERSION = "2027.4.0"
_REFERENCE_COMPONENTS = {"automation", "script"}


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
    entity_id = entity_registry.async_get_entity_id(
        platform_domain, DOMAIN, entity_unique_id
    )
    if entity_id is None:
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    entity_entry = entity_registry.async_get(entity_id)
    if entity_entry is None:
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    if hass.state is not CoreState.running:
        _async_defer_deprecation_check(
            hass,
            entity_registry,
            async_on_unload=async_on_unload,
            platform_domain=platform_domain,
            entity_unique_id=entity_unique_id,
            issue_id=issue_id,
            translation_key=translation_key,
        )
        return True

    return _async_check_deprecated_entity(
        hass,
        entity_registry,
        entity_id=entity_id,
        issue_id=issue_id,
        translation_key=translation_key,
    )


@callback
def _async_check_deprecated_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    *,
    entity_id: str,
    issue_id: str,
    translation_key: str,
) -> bool:
    """Check whether a deprecated entity should remain in the registry."""
    entity_entry = entity_registry.async_get(entity_id)
    if entity_entry is None:
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

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
    """Return markdown list items for automations and scripts."""
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


@callback
def _async_defer_deprecation_check(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    *,
    async_on_unload: Callable[[Callable[[], None]], None],
    platform_domain: str,
    entity_unique_id: str,
    issue_id: str,
    translation_key: str,
) -> None:
    """Recheck entity references after automation and script setup."""
    unsubscribers: list[Callable[[], None]] = []
    loaded_components: set[str] = set()

    @callback
    def _async_recheck() -> None:
        for unsubscribe in unsubscribers:
            unsubscribe()

        if entity_id := entity_registry.async_get_entity_id(
            platform_domain, DOMAIN, entity_unique_id
        ):
            _async_check_deprecated_entity(
                hass,
                entity_registry,
                entity_id=entity_id,
                issue_id=issue_id,
                translation_key=translation_key,
            )
        else:
            async_delete_issue(hass, DOMAIN, issue_id)

    @callback
    def _async_component_loaded(event: Event[EventComponentLoaded]) -> None:
        if (component := event.data[ATTR_COMPONENT]) in _REFERENCE_COMPONENTS:
            loaded_components.add(component)
            if _REFERENCE_COMPONENTS.issubset(loaded_components):
                _async_recheck()

    @callback
    def _async_homeassistant_started(_: Event[NoEventData]) -> None:
        _async_recheck()

    @callback
    def _async_register_unsubscriber(unsubscribe: Callable[[], None]) -> None:
        is_subscribed = True

        @callback
        def _async_unsubscribe() -> None:
            nonlocal is_subscribed
            if is_subscribed:
                is_subscribed = False
                unsubscribe()

        unsubscribers.append(_async_unsubscribe)
        async_on_unload(_async_unsubscribe)

    _async_register_unsubscriber(
        hass.bus.async_listen(EVENT_COMPONENT_LOADED, _async_component_loaded)
    )
    _async_register_unsubscriber(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, _async_homeassistant_started
        )
    )


def plugwise_command[_PlugwiseEntityT: PlugwiseEntity, **_P, _R](
    func: Callable[Concatenate[_PlugwiseEntityT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_PlugwiseEntityT, _P], Coroutine[Any, Any, _R]]:
    """Decorate Plugwise calls that send commands/make changes to the device.

    A decorator that wraps the passed in function, catches Plugwise errors,
    and requests an coordinator update to update status of the devices asap.
    """

    async def handler(
        self: _PlugwiseEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except PlugwiseException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_communicating_with_api",
                translation_placeholders={
                    "error": str(err),
                },
            ) from err
        finally:
            await self.coordinator.async_request_refresh()

    return handler
