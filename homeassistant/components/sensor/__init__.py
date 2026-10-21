"""Component to interface with various sensors that can be monitored."""

from contextlib import suppress
from datetime import timedelta
import logging
from typing import Final, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    AMBIGUOUS_UNITS,
    ATTR_LAST_RESET,
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    CONF_STATE_CLASS,
    DEVICE_CLASS_STATE_CLASSES,
    DEVICE_CLASS_UNITS,
    DEVICE_CLASSES,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    NON_NUMERIC_DEVICE_CLASSES,
    STATE_CLASS_UNITS,
    STATE_CLASSES,
    STATE_CLASSES_SCHEMA,
    UNIT_CONVERTERS,
    SensorDeviceClass,
    SensorEntityCapabilityAttribute,
    SensorEntityStateAttribute,
    SensorStateClass,
)
from .entity import (
    RestoreSensor,
    SensorEntity,
    SensorEntityDescription,
    SensorExtraStoredData,
)
from .websocket_api import async_setup as async_setup_ws_api

_LOGGER: Final = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[SensorEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL: Final = timedelta(seconds=30)

__all__ = [
    "AMBIGUOUS_UNITS",
    "ATTR_LAST_RESET",
    "ATTR_OPTIONS",
    "ATTR_STATE_CLASS",
    "CONF_STATE_CLASS",
    "DEVICE_CLASSES",
    "DEVICE_CLASSES_SCHEMA",
    "DEVICE_CLASS_STATE_CLASSES",
    "DEVICE_CLASS_UNITS",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "NON_NUMERIC_DEVICE_CLASSES",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "STATE_CLASSES",
    "STATE_CLASSES_SCHEMA",
    "STATE_CLASS_UNITS",
    "UNIT_CONVERTERS",
    "RestoreSensor",
    "SensorDeviceClass",
    "SensorEntity",
    "SensorEntityCapabilityAttribute",
    "SensorEntityDescription",
    "SensorEntityStateAttribute",
    "SensorExtraStoredData",
    "SensorStateClass",
    "async_rounded_state",
    "async_update_suggested_units",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for sensors."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[SensorEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    async_setup_ws_api(hass)
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)


@callback
def async_update_suggested_units(hass: HomeAssistant) -> None:
    """Update the suggested_unit_of_measurement according to the unit system."""
    registry = er.async_get(hass)

    for entry in registry.entities.values():
        if entry.domain != DOMAIN:
            continue

        sensor_private_options = dict(entry.options.get(f"{DOMAIN}.private", {}))
        sensor_private_options["refresh_initial_entity_options"] = True
        registry.async_update_entity_options(
            entry.entity_id,
            f"{DOMAIN}.private",
            sensor_private_options,
        )


def _display_precision(hass: HomeAssistant, entity_id: str) -> int | None:
    """Return the display precision."""
    if not (entry := er.async_get(hass).async_get(entity_id)) or not (
        sensor_options := entry.options.get(DOMAIN)
    ):
        return None
    if (display_precision := sensor_options.get("display_precision")) is not None:
        return cast(int, display_precision)
    return sensor_options.get("suggested_display_precision")


@callback
def async_rounded_state(hass: HomeAssistant, entity_id: str, state: State) -> str:
    """Return the state rounded for presentation."""
    value = state.state
    if (precision := _display_precision(hass, entity_id)) is None:
        return value

    with suppress(TypeError, ValueError):
        numerical_value = float(value)
        value = f"{numerical_value:z.{precision}f}"

    return value
