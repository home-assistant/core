"""Map EZVIZ contact sensor names to WINDOW using Home Assistant core i18n.

Reads ``entity_component.window.name`` from every shipped locale under
``homeassistant.components.binary_sensor`` — the same strings the frontend uses for
the *Window* device class — instead of maintaining a custom synonym list.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import unicodedata
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
)
import homeassistant.components.binary_sensor as binary_sensor_component

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DATA_CONTACT_WINDOW_I18N = "contact_window_i18n"

# Normalized Latin window labels → one regex each (deduped).
_LATIN_LABEL_PATTERN = re.compile(r"^[a-z\s\-']+$")
ContactWindowI18n = tuple[tuple[re.Pattern[str], ...], frozenset[str]]


def _normalize_for_latin_match(text: str) -> str:
    """Lowercase and strip combining marks (fenêtre → fenetre)."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _load_window_labels_from_core_translations() -> ContactWindowI18n:
    """Collect *window* device-class names from core binary_sensor translations."""
    trans_dir = pathlib.Path(binary_sensor_component.__file__).parent / "translations"
    seen_latin_norms: set[str] = set()
    patterns: list[re.Pattern[str]] = []
    unicode_substrings: set[str] = set()

    paths = sorted(trans_dir.glob("*.json"))
    for path in paths:
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            continue
        ec = data.get("entity_component") or {}
        win = ec.get("window") or {}
        name = win.get("name")
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name:
            continue

        norm = _normalize_for_latin_match(name)
        if norm and _LATIN_LABEL_PATTERN.fullmatch(norm):
            if norm in seen_latin_norms:
                continue
            seen_latin_norms.add(norm)
            parts = norm.split()
            if len(parts) == 1:
                patterns.append(
                    re.compile(rf"\b{re.escape(parts[0])}\b", re.IGNORECASE)
                )
            else:
                patterns.append(
                    re.compile(
                        r"\b" + r"\s+".join(re.escape(p) for p in parts) + r"\b",
                        re.IGNORECASE,
                    )
                )
        else:
            unicode_substrings.add(name)

    _LOGGER.debug(
        "EZVIZ contact WINDOW i18n: %d Latin patterns, %d unicode phrases from %d files",
        len(patterns),
        len(unicode_substrings),
        len(paths),
    )
    return (tuple(patterns), frozenset(unicode_substrings))


async def async_ensure_contact_window_i18n(hass: HomeAssistant) -> None:
    """Load and cache core translation-derived window labels (once per HA instance)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if DATA_CONTACT_WINDOW_I18N in domain_data:
        return
    domain_data[DATA_CONTACT_WINDOW_I18N] = await hass.async_add_executor_job(
        _load_window_labels_from_core_translations
    )


def infer_contact_sensor_device_class(
    hass: HomeAssistant | None, name: str | None
) -> BinarySensorDeviceClass:
    """Return WINDOW if ``name`` matches a core *window* label in any locale; else DOOR."""
    if not name or not name.strip():
        return BinarySensorDeviceClass.DOOR
    # Entity.__init__ runs before ``self.hass`` is bound; callers must pass coordinator.hass.
    if hass is None:
        return BinarySensorDeviceClass.DOOR

    i18n: ContactWindowI18n | None = hass.data.get(DOMAIN, {}).get(
        DATA_CONTACT_WINDOW_I18N
    )
    if i18n is None:
        _LOGGER.warning(
            "Contact window i18n not loaded; defaulting door_status to DOOR. "
            "Ensure async_ensure_contact_window_i18n ran during binary_sensor setup."
        )
        return BinarySensorDeviceClass.DOOR

    patterns, unicode_substrings = i18n
    name_cf = name.casefold()
    for phrase in unicode_substrings:
        if phrase.casefold() in name_cf:
            return BinarySensorDeviceClass.WINDOW

    normalized_device = _normalize_for_latin_match(name)
    for pattern in patterns:
        if pattern.search(normalized_device):
            return BinarySensorDeviceClass.WINDOW

    return BinarySensorDeviceClass.DOOR
