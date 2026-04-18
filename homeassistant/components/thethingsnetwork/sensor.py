"""The Things Network sensor platform."""

from __future__ import annotations

import logging
from typing import Final, TypedDict, TypeVar, cast

from ttn_client import TTNSensorAttribute, TTNSensorValue

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CONF_APP_ID, DOMAIN
from .coordinator import TTNCoordinator
from .entity import TTNEntity

_LOGGER = logging.getLogger(__name__)

_SENSOR_ATTR_PREFIX: Final = "_sensor_attr_"
_ATTR_KEYS: Final[frozenset[str]] = frozenset(
    {
        "unit",
        "device_class",
        "state_class",
        "entity_category",
        "suggested_display_precision",
        "friendly_name",
    }
)

EnumT = TypeVar("EnumT", SensorDeviceClass, SensorStateClass, EntityCategory)


class SensorAttrDict(TypedDict, total=False):
    """Decoded optional sensor attributes from TTN."""

    unit: str
    device_class: str
    state_class: str
    entity_category: str
    suggested_display_precision: str
    friendly_name: str


VALID_DEVICE_CLASSES: Final[frozenset[str]] = frozenset(
    item.value for item in SensorDeviceClass
)
VALID_STATE_CLASSES: Final[frozenset[str]] = frozenset(
    item.value for item in SensorStateClass
)
VALID_ENTITY_CATEGORIES: Final[frozenset[str]] = frozenset(
    item.value for item in EntityCategory
)


def _parse_enum(enum_cls: type[EnumT], raw: object | None) -> EnumT | None:
    """Parse a raw decoder value into a Home Assistant enum.

    TTN decoder output is external data — invalid or non-string values are possible.
    Invalid values are already warned about by _validate_sensor_attr.
    """
    if raw is None:
        return None

    try:
        return enum_cls(str(raw))
    except (ValueError, TypeError):
        return None


def _extract_sensor_attr(
    fields: dict[str, object],
) -> dict[str, SensorAttrDict]:
    """Extract flattened TTN sensor attribute keys into a nested dict.

    Example:
        _sensor_attr_BatV_unit = TTN_Attr("V")
        _sensor_attr_BatV_device_class = TTN_Attr("voltage")

    Returns:
        {
            "BatV": {
                "unit": "V",
                "device_class": "voltage",
            }
        }
    """
    sensor_attr: dict[str, SensorAttrDict] = {}

    for key, value in fields.items():
        if not isinstance(value, TTNSensorAttribute):
            continue

        if not key.startswith(_SENSOR_ATTR_PREFIX):
            continue

        remainder = key[len(_SENSOR_ATTR_PREFIX) :]

        for attr_key in _ATTR_KEYS:
            if not remainder.endswith(f"_{attr_key}"):
                continue

            field_name = remainder[: -(len(attr_key) + 1)]
            cast(dict[str, str], sensor_attr.setdefault(field_name, {}))[attr_key] = (
                str(value.value)
            )
            break

    return sensor_attr


def _validate_sensor_attr(
    attr: SensorAttrDict, field_name: str, *, device_id: str
) -> None:
    """Log unsupported Home Assistant metadata values from the decoder."""
    if (raw := attr.get("device_class")) and raw not in VALID_DEVICE_CLASSES:
        _LOGGER.warning(
            "Device %s field %s has unsupported device_class=%r",
            device_id,
            field_name,
            raw,
        )

    if (raw := attr.get("state_class")) and raw not in VALID_STATE_CLASSES:
        _LOGGER.warning(
            "Device %s field %s has unsupported state_class=%r",
            device_id,
            field_name,
            raw,
        )

    if (raw := attr.get("entity_category")) and raw not in VALID_ENTITY_CATEGORIES:
        _LOGGER.warning(
            "Device %s field %s has unsupported entity_category=%r",
            device_id,
            field_name,
            raw,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TTN sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors: set[tuple[str, str]] = set()

    def _async_measurement_listener() -> None:
        """Create new entities for newly discovered TTN values."""
        data = coordinator.data
        new_sensors: dict[tuple[str, str], TtnDataSensor] = {}

        for device_id, device_uplinks in data.items():
            sensor_attr = _extract_sensor_attr(device_uplinks)

            for field_id, ttn_value in device_uplinks.items():
                if (device_id, field_id) in sensors:
                    continue

                if field_id.startswith("_"):
                    continue

                if isinstance(ttn_value, TTNSensorAttribute):
                    continue

                if not isinstance(ttn_value, TTNSensorValue):
                    continue

                attr = sensor_attr.get(field_id, {})
                _validate_sensor_attr(attr, field_id, device_id=device_id)

                new_sensors[(device_id, field_id)] = TtnDataSensor(
                    coordinator=coordinator,
                    app_id=entry.data[CONF_APP_ID],
                    ttn_value=ttn_value,
                    attr=attr,
                )

        if new_sensors:
            async_add_entities(new_sensors.values())

        sensors.update(new_sensors.keys())

    entry.async_on_unload(coordinator.async_add_listener(_async_measurement_listener))
    _async_measurement_listener()


class TtnDataSensor(TTNEntity, SensorEntity):
    """Representation of a TTN sensor."""

    _ttn_value: TTNSensorValue

    def __init__(
        self,
        coordinator: TTNCoordinator,
        app_id: str,
        ttn_value: TTNSensorValue,
        attr: SensorAttrDict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, app_id, ttn_value)
        self._ttn_value = ttn_value

        if unit := attr.get("unit"):
            self._attr_native_unit_of_measurement = unit

        if device_class := _parse_enum(SensorDeviceClass, attr.get("device_class")):
            self._attr_device_class = device_class

        if state_class := _parse_enum(SensorStateClass, attr.get("state_class")):
            self._attr_state_class = state_class

        if entity_category := _parse_enum(EntityCategory, attr.get("entity_category")):
            self._attr_entity_category = entity_category

        if precision := attr.get("suggested_display_precision"):
            # Value from TTN decoder JSON, not HA Core — convert to int
            try:
                self._attr_suggested_display_precision = int(precision)
            except ValueError, TypeError:
                _LOGGER.warning(
                    "Invalid suggested_display_precision for %s (unique_id=%s): %r",
                    ttn_value.field_id,
                    self.unique_id,
                    precision,
                )

        if friendly_name := attr.get("friendly_name"):
            self._attr_name = friendly_name

    @property
    def native_value(self) -> StateType:
        """Return the current sensor value."""
        return self._ttn_value.value
