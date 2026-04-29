"""Known sensor unique IDs that have translation support.

Mobile app sensors are dynamically registered by the companion apps. For a
curated set of sensor IDs that the iOS and Android Companion apps use
consistently we provide HA-side translations for the entity name, icon and
(when applicable) state. For all other sensor IDs the integration keeps using
the name/icon supplied by the app.
"""

from __future__ import annotations

from .const import ATTR_SENSOR_TYPE_SENSOR

# Mapping of (entity_type, sensor_unique_id) to translation_key.
# The translation_key must have a matching entry in strings.json under
# entity.<entity_type>.<translation_key>.
KNOWN_SENSORS: dict[tuple[str, str], str] = {
    (ATTR_SENSOR_TYPE_SENSOR, "battery_state"): "battery_state",
    (ATTR_SENSOR_TYPE_SENSOR, "charger_type"): "charger_type",
    (ATTR_SENSOR_TYPE_SENSOR, "ringer_mode"): "ringer_mode",
    (ATTR_SENSOR_TYPE_SENSOR, "audio_mode"): "audio_mode",
}


def get_translation_key(entity_type: str, sensor_unique_id: str) -> str | None:
    """Return the translation key for a known sensor, or None."""
    return KNOWN_SENSORS.get((entity_type, sensor_unique_id))
