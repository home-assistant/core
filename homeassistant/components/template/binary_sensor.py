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
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME_TEMPLATE,
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
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import async_call_later, async_track_point_in_utc_time
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    make_template_entity_common_modern_attributes_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

DEFAULT_NAME = "Template Binary Sensor"

CONF_DELAY_ON = "delay_on"
CONF_DELAY_OFF = "delay_off"
CONF_AUTO_OFF = "auto_off"

LEGACY_FIELDS = {
    CONF_FRIENDLY_NAME_TEMPLATE: CONF_NAME,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

BINARY_SENSOR_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AUTO_OFF): vol.Any(cv.positive_time_period, cv.template),
        vol.Optional(CONF_DELAY_OFF): vol.Any(cv.positive_time_period, cv.template),
        vol.Optional(CONF_DELAY_ON): vol.Any(cv.positive_time_period, cv.template),
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Required(CONF_STATE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)

BINARY_SENSOR_YAML_SCHEMA = BINARY_SENSOR_COMMON_SCHEMA.extend(
    make_template_entity_common_modern_attributes_schema(
        BINARY_SENSOR_DOMAIN, DEFAULT_NAME
    ).schema
)

BINARY_SENSOR_CONFIG_ENTRY_SCHEMA = BINARY_SENSOR_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)

BINARY_SENSOR_LEGACY_YAML_SCHEMA = vol.All(
    cv.deprecated(ATTR_ENTITY_ID),
    vol.Schema(
        {
            vol.Required(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_ICON_TEMPLATE): cv.template,
            vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_DELAY_ON): vol.Any(cv.positive_time_period, cv.template),
            vol.Optional(CONF_DELAY_OFF): vol.Any(cv.positive_time_period, cv.template),
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY.schema)
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema),
)


PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(
            BINARY_SENSOR_LEGACY_YAML_SCHEMA
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template binary sensors."""
    await async_setup_template_platform(
        hass,
        BINARY_SENSOR_DOMAIN,
        config,
        StateBinarySensorEntity,
        TriggerBinarySensorEntity,
        async_add_entities,
        discovery_info,
        LEGACY_FIELDS,
        legacy_key=CONF_SENSORS,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateBinarySensorEntity,
        BINARY_SENSOR_CONFIG_ENTRY_SCHEMA,
    )


@callback
def async_create_preview_binary_sensor(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateBinarySensorEntity:
    """Create a preview sensor."""
    return async_setup_template_preview(
        hass, name, config, StateBinarySensorEntity, BINARY_SENSOR_CONFIG_ENTRY_SCHEMA
    )


class AbstractTemplateBinarySensor(
    AbstractTemplateEntity, BinarySensorEntity, RestoreEntity
):
    """Representation of a template binary sensor features."""

    _entity_id_format = ENTITY_ID_FORMAT

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._template: template.Template = config[CONF_STATE]
        self._delay_cancel: CALLBACK_TYPE | None = None


class StateBinarySensorEntity(TemplateEntity, AbstractTemplateBinarySensor):
    """A virtual binary sensor that triggers from another sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the Template binary sensor."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateBinarySensor.__init__(self, config)
        self._delay_on = None
        self._delay_on_template = config.get(CONF_DELAY_ON)
        self._delay_off = None
        self._delay_off_template = config.get(CONF_DELAY_OFF)

    async def async_added_to_hass(self) -> None:
        """Restore state."""
        if (
            (
                self._delay_on_template is not None
                or self._delay_off_template is not None
            )
            and (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            self._attr_is_on = last_state.state == STATE_ON
        await super().async_added_to_hass()

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute("_state", self._template, None, self._update_state)

        if self._delay_on_template is not None:
            try:
                self._delay_on = cv.positive_time_period(self._delay_on_template)
            except vol.Invalid:
                self.add_template_attribute(
                    "_delay_on", self._delay_on_template, cv.positive_time_period
                )

        if self._delay_off_template is not None:
            try:
                self._delay_off = cv.positive_time_period(self._delay_off_template)
            except vol.Invalid:
                self.add_template_attribute(
                    "_delay_off", self._delay_off_template, cv.positive_time_period
                )

        super()._async_setup_templates()

    @callback
    def _update_state(self, result):
        super()._update_state(result)

        if self._delay_cancel:
            self._delay_cancel()
            self._delay_cancel = None

        state: bool | None = None
        if result is not None and not isinstance(result, TemplateError):
            state = template.result_as_boolean(result)

        if state == self._attr_is_on:
            return

        # state without delay
        if (
            state is None
            or (state and not self._delay_on)
            or (not state and not self._delay_off)
        ):
            self._attr_is_on = state
            return

        @callback
        def _set_state(_):
            """Set state of template binary sensor."""
            self._attr_is_on = state
            self.async_write_ha_state()

        delay = (self._delay_on if state else self._delay_off).total_seconds()
        # state with delay. Cancelled if template result changes.
        self._delay_cancel = async_call_later(self.hass, delay, _set_state)


class TriggerBinarySensorEntity(TriggerEntity, AbstractTemplateBinarySensor):
    """Sensor entity based on trigger data."""

    domain = BINARY_SENSOR_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateBinarySensor.__init__(self, config)

        for key in (CONF_STATE, CONF_DELAY_ON, CONF_DELAY_OFF, CONF_AUTO_OFF):
            if isinstance(config.get(key), template.Template):
                self._to_render_simple.append(key)
                self._parse_result.add(key)

        self._last_delay_from: bool | None = None
        self._last_delay_to: bool | None = None
        self._auto_off_cancel: CALLBACK_TYPE | None = None
        self._auto_off_time: datetime | None = None

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
            and self._attr_is_on is None
        ):
            self._attr_is_on = last_state.state == STATE_ON
            self.restore_attributes(last_state)

            if CONF_AUTO_OFF not in self._config:
                return

            if (
                auto_off_time := extra_data.auto_off_time
            ) is not None and auto_off_time <= dt_util.utcnow():
                # It's already past the saved auto off time
                self._attr_is_on = False

            if self._attr_is_on and auto_off_time is not None:
                self._set_auto_off(auto_off_time)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        raw = self._rendered.get(CONF_STATE)
        state: bool | None = None
        if raw is not None:
            state = template.result_as_boolean(raw)

        key = CONF_DELAY_ON if state else CONF_DELAY_OFF
        delay = self._rendered.get(key) or self._config.get(key)

        if (
            self._delay_cancel
            and delay
            and self._attr_is_on == self._last_delay_from
            and state == self._last_delay_to
        ):
            return

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

        # state without delay.
        if self._attr_is_on == state or delay is None:
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
        self._last_delay_from = self._attr_is_on
        self._last_delay_to = state
        self._delay_cancel = async_call_later(
            self.hass, delay.total_seconds(), partial(self._set_state, state)
        )

    @callback
    def _set_state(self, state, _=None):
        """Set up auto off."""
        self._attr_is_on = state
        self._delay_cancel = None
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
            self._attr_is_on = False
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
        auto_off_time: datetime | dict[str, str] | None = self.auto_off_time
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
