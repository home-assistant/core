"""Source order and sensor detection for the weather at home."""

from typing import Any

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import Integration, async_get_integrations

from .const import AIR_QUALITY_CATEGORY, AIR_QUALITY_DEVICE_CLASSES
from .data import WeatherDataPreferences

ATTR_STATE_CLASS = "state_class"


def _is_user_facing(entity_registry: er.EntityRegistry, entity_id: str) -> bool:
    """Return if an entity is meant to be shown to users."""
    entry = entity_registry.async_get(entity_id)
    return entry is None or (entry.hidden_by is None and entry.entity_category is None)


def async_get_sources(hass: HomeAssistant, prefs: WeatherDataPreferences) -> list[str]:
    """Return the weather entities in order of preference.

    Weather entities that are not ordered yet follow the ordered ones, so a new
    weather service shows up without extra steps.
    """
    entity_registry = er.async_get(hass)
    excluded = set(prefs["excluded_weather_entities"])
    available = sorted(
        entity_id
        for entity_id in hass.states.async_entity_ids(WEATHER_DOMAIN)
        if entity_id not in excluded and _is_user_facing(entity_registry, entity_id)
    )
    ordered = [
        entity_id for entity_id in prefs["weather_entities"] if entity_id in available
    ]
    return ordered + [entity_id for entity_id in available if entity_id not in ordered]


def _user_facing_sensors(hass: HomeAssistant) -> list[State]:
    """Return the sensors meant for users, sorted by entity ID."""
    entity_registry = er.async_get(hass)
    return sorted(
        (
            state
            for state in hass.states.async_all(SENSOR_DOMAIN)
            if _is_user_facing(entity_registry, state.entity_id)
        ),
        key=lambda state: state.entity_id,
    )


def _find_rain_gauge(hass: HomeAssistant) -> str | None:
    """Return a precipitation sensor that adds up rain.

    Weather services report precipitation as a rate or a forecast, so those
    are skipped.
    """
    for state in _user_facing_sensors(hass):
        if state.attributes.get(
            ATTR_DEVICE_CLASS
        ) == SensorDeviceClass.PRECIPITATION and state.attributes.get(
            ATTR_STATE_CLASS
        ) in (SensorStateClass.TOTAL, SensorStateClass.TOTAL_INCREASING):
            return state.entity_id
    return None


async def _air_quality_sensors(hass: HomeAssistant) -> list[State]:
    """Return sensors from integrations in the air quality category.

    Indoor air purifiers also measure particles, so only services from the air
    quality category count.
    """
    entity_registry = er.async_get(hass)
    sensors = _user_facing_sensors(hass)
    platforms: dict[str, str] = {}
    for state in sensors:
        if entry := entity_registry.async_get(state.entity_id):
            platforms[state.entity_id] = entry.platform

    integrations = await async_get_integrations(hass, set(platforms.values()))
    air_quality_domains = {
        domain
        for domain, integration in integrations.items()
        if isinstance(integration, Integration)
        and AIR_QUALITY_CATEGORY in integration.categories
    }
    return [
        state
        for state in sensors
        if platforms.get(state.entity_id) in air_quality_domains
    ]


def _find_air_quality(sensors: list[State]) -> list[str]:
    """Return one air quality sensor per device class."""
    by_device_class: dict[str, str] = {}
    for state in sensors:
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        if device_class in AIR_QUALITY_DEVICE_CLASSES:
            by_device_class.setdefault(device_class, state.entity_id)
    return [
        by_device_class[device_class]
        for device_class in AIR_QUALITY_DEVICE_CLASSES
        if device_class in by_device_class
    ]


def _find_pollen(hass: HomeAssistant, sensors: list[State]) -> list[str]:
    """Return pollen sensors.

    There is no device class for pollen, so this matches the translation key,
    or the entity ID when there is no translation key.
    """
    entity_registry = er.async_get(hass)
    pollen: list[str] = []
    for state in sensors:
        entry = entity_registry.async_get(state.entity_id)
        name = (entry and entry.translation_key) or state.entity_id
        if "pollen" in name.lower():
            pollen.append(state.entity_id)
    return pollen


async def async_get_info(
    hass: HomeAssistant, prefs: WeatherDataPreferences
) -> dict[str, Any]:
    """Return the source order and the sensors, selected or detected."""
    rain_gauge: str | None
    if "rain_gauge_entity" in prefs:
        rain_gauge = prefs["rain_gauge_entity"]
        if rain_gauge is not None and hass.states.get(rain_gauge) is None:
            rain_gauge = None
    else:
        rain_gauge = _find_rain_gauge(hass)

    air_quality: list[str] | None = prefs.get("air_quality_entities")
    pollen: list[str] | None = prefs.get("pollen_entities")
    if air_quality is None or pollen is None:
        sensors = await _air_quality_sensors(hass)
        if air_quality is None:
            air_quality = _find_air_quality(sensors)
        if pollen is None:
            pollen = _find_pollen(hass, sensors)

    return {
        "sources": async_get_sources(hass, prefs),
        "rain_gauge": rain_gauge,
        "air_quality": [
            entity_id for entity_id in air_quality if hass.states.get(entity_id)
        ],
        "pollen": [entity_id for entity_id in pollen if hass.states.get(entity_id)],
    }
