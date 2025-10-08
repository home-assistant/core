"""Icon helper methods."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from functools import lru_cache
import logging
import pathlib
from typing import Any, cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import Integration, async_get_integrations
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import load_json_object

from .translation import build_resources

ICON_CACHE: HassKey[_IconsCache] = HassKey("icon_cache")

_LOGGER = logging.getLogger(__name__)


def convert_shorthand_service_icon(
    value: str | dict[str, str | dict[str, str]],
) -> dict[str, str | dict[str, str]]:
    """Convert shorthand service icon to dict."""
    if isinstance(value, str):
        return {"service": value}
    return value


def _load_icons_file(
    icons_file: pathlib.Path,
) -> dict[str, Any]:
    """Load and parse an icons.json file."""
    icons = load_json_object(icons_file)
    if "services" not in icons:
        return icons
    services = cast(dict[str, str | dict[str, str | dict[str, str]]], icons["services"])
    for service, service_icons in services.items():
        services[service] = convert_shorthand_service_icon(service_icons)
    return icons


def _load_icons_files(
    icons_files: dict[str, pathlib.Path],
) -> dict[str, dict[str, Any]]:
    """Load and parse icons.json files."""
    return {
        component: _load_icons_file(icons_file)
        for component, icons_file in icons_files.items()
    }


async def _async_get_component_icons(
    hass: HomeAssistant,
    components: set[str],
    integrations: dict[str, Integration],
) -> dict[str, Any]:
    """Load icons."""
    icons: dict[str, Any] = {}

    # Determine files to load
    files_to_load = {
        comp: integrations[comp].file_path / "icons.json" for comp in components
    }

    # Load files
    if files_to_load:
        icons.update(
            await hass.async_add_executor_job(_load_icons_files, files_to_load)
        )

    return icons


class _IconsCache:
    """Cache for icons."""

    __slots__ = ("_cache", "_hass", "_loaded", "_lock")

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the cache."""
        self._hass = hass
        self._loaded: set[str] = set()
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def async_fetch(
        self,
        category: str,
        components: set[str],
    ) -> dict[str, dict[str, Any]]:
        """Load resources into the cache."""
        if components_to_load := components - self._loaded:
            # Icons are never unloaded so if there are no components to load
            # we can skip the lock which reduces contention
            async with self._lock:
                # Check components to load again, as another task might have loaded
                # them while we were waiting for the lock.
                if components_to_load := components - self._loaded:
                    await self._async_load(components_to_load)

        return {
            component: result
            for component in components
            if (result := self._cache.get(category, {}).get(component))
        }

    async def _async_load(self, components: set[str]) -> None:
        """Populate the cache for a given set of components."""
        _LOGGER.debug("Cache miss for: %s", components)

        integrations: dict[str, Integration] = {}
        ints_or_excs = await async_get_integrations(self._hass, components)
        for domain, int_or_exc in ints_or_excs.items():
            if isinstance(int_or_exc, Exception):
                raise int_or_exc
            integrations[domain] = int_or_exc

        icons = await _async_get_component_icons(self._hass, components, integrations)

        self._build_category_cache(components, icons)
        self._loaded.update(components)

    @callback
    def _build_category_cache(
        self,
        components: set[str],
        icons: dict[str, dict[str, Any]],
    ) -> None:
        """Extract resources into the cache."""
        categories = {
            category for component in icons.values() for category in component
        }
        for category in categories:
            self._cache.setdefault(category, {}).update(
                build_resources(icons, components, category)
            )


async def async_get_icons(
    hass: HomeAssistant,
    category: str,
    integrations: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return all icons of integrations.

    If integration specified, load it for that one; otherwise default to loaded
    integrations.
    """
    if integrations:
        components = set(integrations)
    else:
        components = hass.config.top_level_components

    if ICON_CACHE in hass.data:
        cache = hass.data[ICON_CACHE]
    else:
        cache = hass.data[ICON_CACHE] = _IconsCache(hass)

    return await cache.async_fetch(category, components)


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
