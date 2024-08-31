"""Common functions for history."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from ... import recorder


def _schema_version(hass: HomeAssistant) -> int:
    return recorder.get_instance(hass).schema_version
