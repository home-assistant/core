"""Support for exposing a templated binary sensor."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any, Self

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_FRIENDLY_NAME_TEMPLATE,
    CONF_ICON,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_SENSORS,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_point_in_utc_time
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import TriggerUpdateCoordinator
from .const import (
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_OBJECT_ID,
    CONF_PICTURE,
)
from .template_entity import (
    TEMPLATE_ENTITY_COMMON_SCHEMA,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)
from .trigger_entity import TriggerEntity

CONF_DELAY_ON = "delay_on"
CONF_DELAY_OFF = "delay_off"
CONF_AUTO_OFF = "auto_off"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"

LEGACY_FIELDS = {
    CONF_ICON_TEMPLATE: CONF_ICON,
    CONF_ENTITY_PICTURE_TEMPLATE: CONF_PICTURE,
    CONF_AVAILABILITY_TEMPLATE: CONF_AVAILABILITY,
    CONF_ATTRIBUTE_TEMPLATES: CONF_ATTRIBUTES,
    CONF_FRIENDLY_NAME_TEMPLATE: CONF_NAME,
    CONF_FRIENDLY_NAME: CONF_NAME,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AUTO_OFF): vol.Any(cv.positive_time_period, cv.template),
        vol.Optional(CONF_DELAY_OFF): vol.Any(cv.positive_time_period, cv.template),
        vol.Optional(CONF_DELAY_ON): vol.Any(cv.positive_time_period, cv.template),
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Required(CONF_STATE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
).extend(TEMPLATE_ENTITY_COMMON_SCHEMA.schema)

LEGACY_BINARY_SENSOR_SCHEMA = vol.All(
    cv.deprecated(ATTR_ENTITY_ID),
    vol.Schema(
        {
            vol.Required(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_ICON_TEMPLATE): cv.template,
            vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
            vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
            vol.Optional(CONF_ATTRIBUTE_TEMPLATES): vol.Schema(
                {cv.string: cv.template}
            ),
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_DELAY_ON): vol.Any(cv.positive_time_period, cv.template),
            vol.Optional(CONF_DELAY_OFF): vol.Any(cv.positive_time_period, cv.template),
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
)


def rewrite_legacy_to_modern_conf(cfg: dict[str, dict]) -> list[dict]:
    """Rewrite legacy binary sensor definitions to modern ones."""
    sensors = []

    for object_id, entity_cfg in cfg.items():
        entity_cfg = {**entity_cfg, CONF_OBJECT_ID: object_id}

        entity_cfg = rewrite_common_legacy_to_modern_conf(entity_cfg, LEGACY_FIELDS)

        if CONF_NAME not in entity_cfg:
            entity_cfg[CONF_NAME] = template.Template(object_id)

        sensors.append(entity_cfg)

    return sensors


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(
            LEGACY_BINARY_SENSOR_SCHEMA
        ),
    }
)


@callback
def _async_create_template_tracking_entities(
    async_add_entities: AddEntitiesCallback,
    hass: HomeAssistant,
    definitions: list[dict],
    unique_id_prefix: str | None,
) -> None:
    """Create the template binary sensors."""
    sensors = []

    for entity_conf in definitions:
        unique_id = entity_conf.get(CONF_UNIQUE_ID)

        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"

        sensors.append(
            BinarySensorTemplate(
                hass,
                entity_conf,
                unique_id,
            )
        )

    async_add_entities(sensors)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template binary sensors."""
    if discovery_info is None:
        _async_create_template_tracking_entities(
            async_add_entities,
            hass,
            rewrite_legacy_to_modern_conf(config[CONF_SENSORS]),
            None,
        )
        return

    if "coordinator" in discovery_info:
        async_add_entities(
            TriggerBinarySensorEntity(hass, discovery_info["coordinator"], config)
            for config in discovery_info["entities"]
        )
        return

    _async_create_template_tracking_entities(
        async_add_entities,
        hass,
        discovery_info["entities"],
        discovery_info["unique_id"],
    )


class BinarySensorTemplate(TemplateEntity, BinarySensorEntity, RestoreEntity):
    """A virtual binary sensor that triggers from another sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the Template binary sensor."""
        super().__init__(hass, config=config, unique_id=unique_id)
        if (object_id := config.get(CONF_OBJECT_ID)) is not None:
            self.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, object_id, hass=hass
            )

        self._device_class: BinarySensorDeviceClass | None = config.get(
            CONF_DEVICE_CLASS
        )
        self._template = config[CONF_STATE]
        self._state: bool | None = None
        self._delay_cancel = None
        self._delay_on = None
        self._delay_on_raw = config.get(CONF_DELAY_ON)
        self._delay_off = None
        self._delay_off_raw = config.get(CONF_DELAY_OFF)

    async def async_added_to_hass(self) -> None:
        """Restore state."""
        if (
            (self._delay_on_raw is not None or self._delay_off_raw is not None)
            and (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            self._state = last_state.state == STATE_ON
        await super().async_added_to_hass()

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute("_state", self._template, None, self._update_state)

        if self._delay_on_raw is not None:
            try:
                self._delay_on = cv.positive_time_period(self._delay_on_raw)
            except vol.Invalid:
                self.add_template_attribute(
                    "_delay_on", self._delay_on_raw, cv.positive_time_period
                )

        if self._delay_off_raw is not None:
            try:
                self._delay_off = cv.positive_time_period(self._delay_off_raw)
            except vol.Invalid:
                self.add_template_attribute(
                    "_delay_off", self._delay_off_raw, cv.positive_time_period
                )

        super()._async_setup_templates()

    @callback
    def _update_state(self, result):
        super()._update_state(result)

        if self._delay_cancel:
            self._delay_cancel()
            self._delay_cancel = None

        state = (
            None
            if isinstance(result, TemplateError)
            else template.result_as_boolean(result)
        )

        if state == self._state:
            return

        # state without delay
        if (
            state is None
            or (state and not self._delay_on)
            or (not state and not self._delay_off)
        ):
            self._state = state
            return

        @callback
        def _set_state(_):
            """Set state of template binary sensor."""
            self._state = state
            self.async_write_ha_state()

        delay = (self._delay_on if state else self._delay_off).total_seconds()
        # state with delay. Cancelled if template result changes.
        self._delay_cancel = async_call_later(self.hass, delay, _set_state)

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the sensor class of the binary sensor."""
        return self._device_class


class TriggerBinarySensorEntity(TriggerEntity, BinarySensorEntity, RestoreEntity):
    """Sensor entity based on trigger data."""

    domain = BINARY_SENSOR_DOMAIN
    extra_template_keys = (CONF_STATE,)

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        super().__init__(hass, coordinator, config)

        for key in (CONF_DELAY_ON, CONF_DELAY_OFF, CONF_AUTO_OFF):
            if isinstance(config.get(key), template.Template):
                self._to_render_simple.append(key)
                self._parse_result.add(key)

        self._delay_cancel: CALLBACK_TYPE | None = None
        self._auto_off_cancel: CALLBACK_TYPE | None = None
        self._auto_off_time: datetime | None = None
        self._state: bool | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            (last_state := await self.async_get_last_state()) is not None
            and (extra_data := await self.async_get_last_binary_sensor_data())
            is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            # The trigger might have fired already while we waited for stored data,
            # then we should not restore state
            and self._state is None
        ):
            self._state = last_state.state == STATE_ON
            self.restore_attributes(last_state)

            if CONF_AUTO_OFF not in self._config:
                return

            if (
                auto_off_time := extra_data.auto_off_time
            ) is not None and auto_off_time <= dt_util.utcnow():
                # It's already past the saved auto off time
                self._state = False

            if self._state and auto_off_time is not None:
                self._set_auto_off(auto_off_time)

    @property
    def is_on(self) -> bool | None:
        """Return state of the sensor."""
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if self._delay_cancel:
            self._delay_cancel()
            self._delay_cancel = None

        if self._auto_off_cancel:
            self._auto_off_cancel()
            self._auto_off_cancel = None
            self._auto_off_time = None

        if not self.available:
            self.async_write_ha_state()
            return

        raw = self._rendered.get(CONF_STATE)
        state = template.result_as_boolean(raw)

        key = CONF_DELAY_ON if state else CONF_DELAY_OFF
        delay = self._rendered.get(key) or self._config.get(key)

        # state without delay. None means rendering failed.
        if self._state == state or state is None or delay is None:
            self._set_state(state)
            return

        if not isinstance(delay, timedelta):
            try:
                delay = cv.positive_time_period(delay)
            except vol.Invalid as err:
                logging.getLogger(__name__).warning(
                    "Error rendering %s template: %s", key, err
                )
                return

        # state with delay. Cancelled if new trigger received
        self._delay_cancel = async_call_later(
            self.hass, delay.total_seconds(), partial(self._set_state, state)
        )

    @callback
    def _set_state(self, state, _=None):
        """Set up auto off."""
        self._state = state
        self.async_set_context(self.coordinator.data["context"])
        self.async_write_ha_state()

        if not state:
            return

        auto_off_delay = self._rendered.get(CONF_AUTO_OFF) or self._config.get(
            CONF_AUTO_OFF
        )

        if auto_off_delay is None:
            return

        if not isinstance(auto_off_delay, timedelta):
            try:
                auto_off_delay = cv.positive_time_period(auto_off_delay)
            except vol.Invalid as err:
                logging.getLogger(__name__).warning(
                    "Error rendering %s template: %s", CONF_AUTO_OFF, err
                )
                return

        auto_off_time = dt_util.utcnow() + auto_off_delay
        self._set_auto_off(auto_off_time)

    def _set_auto_off(self, auto_off_time: datetime) -> None:
        @callback
        def _auto_off(_):
            """Reset state of template binary sensor."""
            self._state = False
            self.async_write_ha_state()

        self._auto_off_time = auto_off_time
        self._auto_off_cancel = async_track_point_in_utc_time(
            self.hass, _auto_off, self._auto_off_time
        )

    @property
    def extra_restore_state_data(self) -> AutoOffExtraStoredData:
        """Return specific state data to be restored."""
        return AutoOffExtraStoredData(self._auto_off_time)

    async def async_get_last_binary_sensor_data(
        self,
    ) -> AutoOffExtraStoredData | None:
        """Restore auto_off_time."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return AutoOffExtraStoredData.from_dict(restored_last_extra_data.as_dict())


@dataclass
class AutoOffExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    auto_off_time: datetime | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of additional data."""
        auto_off_time: datetime | None | dict[str, str] = self.auto_off_time
        if isinstance(auto_off_time, datetime):
            auto_off_time = {
                "__type": str(type(auto_off_time)),
                "isoformat": auto_off_time.isoformat(),
            }
        return {
            "auto_off_time": auto_off_time,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored binary sensor state from a dict."""
        try:
            auto_off_time = restored["auto_off_time"]
        except KeyError:
            return None
        try:
            type_ = auto_off_time["__type"]
            if type_ == "<class 'datetime.datetime'>":
                auto_off_time = dt_util.parse_datetime(auto_off_time["isoformat"])
        except TypeError:
            # native_value is not a dict
            pass
        except KeyError:
            # native_value is a dict, but does not have all values
            return None

        return cls(auto_off_time)
