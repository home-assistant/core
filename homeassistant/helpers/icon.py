"""Icon helper methods."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from functools import lru_cache
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import Integration, async_get_integrations
from homeassistant.util.json import load_json

from .translation import build_resources, recursive_flatten

ICON_LOAD_LOCK = "icon_load_lock"
ICON_FLATTEN_CACHE = "icon_flatten_cache"

_LOGGER = logging.getLogger(__name__)


@callback
def component_icons_path(component: str, integration: Integration) -> str | None:
    """Return the icons json file location for a component.

    Ex: components/hue/icons.json
    If component is just a single file, will return None.
    """
    domain = component.rpartition(".")[-1]

    # If it's a component that is just one file, we don't support icons
    # Example custom_components/my_component.py
    if integration.file_path.name != domain:
        return None

    return str(integration.file_path / "icons.json")


def load_icons_files(icons_files: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Load and parse icons.json files."""
    loaded = {}
    for component, icons_file in icons_files.items():
        loaded_json = load_json(icons_file)

        if not isinstance(loaded_json, dict):
            _LOGGER.warning(
                "Icons file is unexpected type %s. Expected dict for %s",
                type(loaded_json),
                icons_file,
            )
            continue

        loaded[component] = loaded_json

    return loaded


async def _async_get_component_icons(
    hass: HomeAssistant,
    components: set[str],
    integrations: dict[str, Integration],
) -> dict[str, Any]:
    """Load icons."""
    icons: dict[str, Any] = {}

    # Determine files to load
    files_to_load = {}
    for loaded in components:
        domain = loaded.rpartition(".")[-1]
        if (path := component_icons_path(loaded, integrations[domain])) is None:
            icons[loaded] = {}
        else:
            files_to_load[loaded] = path

    if not files_to_load:
        return icons

    # Load files
    if load_icons_job := hass.async_add_executor_job(load_icons_files, files_to_load):
        icons |= await load_icons_job

    return icons


class _IconsCache:
    """Cache for flattened icons."""

    __slots__ = ("hass", "loaded", "cache")

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the cache."""
        self.hass = hass
        self.loaded: set[str] = set()
        self.cache: dict[str, dict[str, Any]] = {}

    async def async_fetch(
        self,
        category: str,
        components: set[str],
    ) -> list[dict[str, dict[str, Any]]]:
        """Load resources into the cache."""
        if components_to_load := components - self.loaded:
            await self._async_load(components_to_load)

        return [
            self.cache.get(component, {}).get(category, {}) for component in components
        ]

    async def _async_load(self, components: set[str]) -> None:
        """Populate the cache for a given set of components."""
        _LOGGER.debug(
            "Cache miss for: %s",
            ", ".join(components),
        )

        integrations: dict[str, Integration] = {}
        domains = list({loaded.rpartition(".")[-1] for loaded in components})
        ints_or_excs = await async_get_integrations(self.hass, domains)
        for domain, int_or_exc in ints_or_excs.items():
            if isinstance(int_or_exc, Exception):
                raise int_or_exc
            integrations[domain] = int_or_exc

        icons = await _async_get_component_icons(self.hass, components, integrations)

        self._build_category_cache(components, icons)

        self.loaded.update(components)

    @callback
    def _build_category_cache(
        self,
        components: set[str],
        icons: dict[str, dict[str, Any]],
    ) -> None:
        """Extract resources into the cache."""
        resource: dict[str, Any] | str
        categories: set[str] = set()
        for resource in icons.values():
            categories.update(resource)

        for category in categories:
            new_resources = build_resources(icons, components, category)
            for component, resource in new_resources.items():
                category_cache: dict[str, Any] = self.cache.setdefault(
                    component, {}
                ).setdefault(category, {})

                if isinstance(resource, dict):
                    category_cache |= recursive_flatten(
                        f"component.{component}.{category}.",
                        resource,
                    )
                else:
                    category_cache[f"component.{component}.{category}"] = resource


async def async_get_icons(
    hass: HomeAssistant,
    category: str,
    integrations: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return all icons of integrations.

    If integration specified, load it for that one; otherwise default to loaded
    intgrations.
    """
    lock = hass.data.setdefault(ICON_LOAD_LOCK, asyncio.Lock())

    if integrations:
        components = set(integrations)
    else:
        components = set(hass.config.components)

    async with lock:
        if ICON_FLATTEN_CACHE in hass.data:
            cache = hass.data[ICON_FLATTEN_CACHE]
        else:
            cache = hass.data[ICON_FLATTEN_CACHE] = _IconsCache(hass)
        cached = await cache.async_fetch(category, components)

    result: dict[str, Any] = {}
    for entry in cached:
        result |= entry
    return result


@lru_cache
def icon_for_battery_level(
    battery_level: int | None = None, charging: bool = False
) -> str:
    """Return a battery icon valid identifier."""
    icon = "mdi:battery"
    if battery_level is None:
        return f"{icon}-unknown"
    if charging and battery_level > 10:
        icon += f"-charging-{int(round(battery_level / 20 - 0.01)) * 20}"
    elif charging:
        icon += "-outline"
    elif battery_level <= 5:
        icon += "-alert"
    elif 5 < battery_level < 95:
        icon += f"-{int(round(battery_level / 10 - 0.01)) * 10}"
    return icon


def icon_for_signal_level(signal_level: int | None = None) -> str:
    """Return a signal icon valid identifier."""
    if signal_level is None or signal_level == 0:
        return "mdi:signal-cellular-outline"
    if signal_level > 70:
        return "mdi:signal-cellular-3"
    if signal_level > 30:
        return "mdi:signal-cellular-2"
    return "mdi:signal-cellular-1"
