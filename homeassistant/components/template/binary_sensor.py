"""Support for exposing a templated binary sensor."""
from __future__ import annotations

from datetime import timedelta
from functools import partial
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.components.template import TriggerUpdateCoordinator
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
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_OBJECT_ID,
    CONF_PICTURE,
)
from .template_entity import TEMPLATE_ENTITY_COMMON_SCHEMA, TemplateEntity
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
        vol.Optional(CONF_NAME): cv.template,
        vol.Required(CONF_STATE): cv.template,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
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

        for from_key, to_key in LEGACY_FIELDS.items():
            if from_key not in entity_cfg or to_key in entity_cfg:
                continue

            val = entity_cfg.pop(from_key)
            if isinstance(val, str):
                val = template.Template(val)
            entity_cfg[to_key] = val

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
    async_add_entities, hass, definitions: list[dict], unique_id_prefix: str | None
):
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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
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


class BinarySensorTemplate(TemplateEntity, BinarySensorEntity):
    """A virtual binary sensor that triggers from another sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the Template binary sensor."""
        super().__init__(config=config)
        if (object_id := config.get(CONF_OBJECT_ID)) is not None:
            self.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, object_id, hass=hass
            )

        self._name: str | None = None
        self._friendly_name_template = config.get(CONF_NAME)

        # Try to render the name as it can influence the entity ID
        if self._friendly_name_template:
            self._friendly_name_template.hass = hass
            try:
                self._name = self._friendly_name_template.async_render(
                    parse_result=False
                )
            except template.TemplateError:
                pass

        self._device_class = config.get(CONF_DEVICE_CLASS)
        self._template = config[CONF_STATE]
        self._state = None
        self._delay_cancel = None
        self._delay_on = None
        self._delay_on_raw = config.get(CONF_DELAY_ON)
        self._delay_off = None
        self._delay_off_raw = config.get(CONF_DELAY_OFF)
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.add_template_attribute("_state", self._template, None, self._update_state)
        if (
            self._friendly_name_template is not None
            and not self._friendly_name_template.is_static
        ):
            self.add_template_attribute("_name", self._friendly_name_template)

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

        await super().async_added_to_hass()

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
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this binary sensor."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the sensor class of the binary sensor."""
        return self._device_class


class TriggerBinarySensorEntity(TriggerEntity, BinarySensorEntity):
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

        self._delay_cancel = None
        self._auto_off_cancel = None
        self._state = False

    @property
    def is_on(self) -> bool:
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

        auto_off_time = self._rendered.get(CONF_AUTO_OFF) or self._config.get(
            CONF_AUTO_OFF
        )

        if auto_off_time is None:
            return

        if not isinstance(auto_off_time, timedelta):
            try:
                auto_off_time = cv.positive_time_period(auto_off_time)
            except vol.Invalid as err:
                logging.getLogger(__name__).warning(
                    "Error rendering %s template: %s", CONF_AUTO_OFF, err
                )
                return

        @callback
        def _auto_off(_):
            """Set state of template binary sensor."""
            self._state = False
            self.async_write_ha_state()

        self._auto_off_cancel = async_call_later(
            self.hass, auto_off_time.total_seconds(), _auto_off
        )
