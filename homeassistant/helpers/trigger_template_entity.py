"""TemplateEntity utility class."""

from __future__ import annotations

import contextlib
import itertools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    STATE_CLASSES_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from . import config_validation as cv
from .entity import Entity
from .template import _SENTINEL, TemplateStateFromEntityId, render_complex
from .typing import ConfigType

CONF_AVAILABILITY = "availability"
CONF_ATTRIBUTES = "attributes"
CONF_PICTURE = "picture"

CONF_TO_ATTRIBUTE = {
    CONF_ICON: ATTR_ICON,
    CONF_NAME: ATTR_FRIENDLY_NAME,
    CONF_PICTURE: ATTR_ENTITY_PICTURE,
}

TEMPLATE_ENTITY_BASE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ICON): cv.template,
        vol.Optional(CONF_NAME): cv.template,
        vol.Optional(CONF_PICTURE): cv.template,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


def make_template_entity_base_schema(default_name: str) -> vol.Schema:
    """Return a schema with default name."""
    return vol.Schema(
        {
            vol.Optional(CONF_ICON): cv.template,
            vol.Optional(CONF_NAME, default=default_name): cv.template,
            vol.Optional(CONF_PICTURE): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )


def log_triggered_template_error(
    entity_id: str,
    err: TemplateError,
    key: str | None = None,
    attribute: str | None = None,
) -> None:
    """Log a trigger entity template error."""
    target = ""
    if key:
        target = f" {key}"
    elif attribute:
        target = f" {CONF_ATTRIBUTES}.{attribute}"

    logging.getLogger(f"{__package__}.{entity_id.split('.')[0]}").error(
        "Error rendering%s template for %s: %s",
        target,
        entity_id,
        err,
    )


TEMPLATE_SENSOR_BASE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
).extend(TEMPLATE_ENTITY_BASE_SCHEMA.schema)


class TriggerBaseEntity(Entity):
    """Template Base entity based on trigger data."""

    domain: str
    extra_template_keys: tuple[str, ...] | None = None
    extra_template_keys_complex: tuple[str, ...] | None = None
    _unique_id: str | None

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        self.hass = hass

        self._set_unique_id(config.get(CONF_UNIQUE_ID))

        self._config = config

        self._static_rendered = {}
        self._to_render_simple: list[str] = []
        self._to_render_complex: list[str] = []

        for itm in (
            CONF_AVAILABILITY,
            CONF_ICON,
            CONF_NAME,
            CONF_PICTURE,
        ):
            if itm not in config or config[itm] is None:
                continue
            if config[itm].is_static:
                self._static_rendered[itm] = config[itm].template
            else:
                self._to_render_simple.append(itm)

        if self.extra_template_keys is not None:
            self._to_render_simple.extend(self.extra_template_keys)

        if self.extra_template_keys_complex is not None:
            self._to_render_complex.extend(self.extra_template_keys_complex)

        # We make a copy so our initial render is 'unknown' and not 'unavailable'
        self._rendered = dict(self._static_rendered)
        self._parse_result = {CONF_AVAILABILITY}
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

    @property
    def name(self) -> str | None:
        """Name of the entity."""
        return self._rendered.get(CONF_NAME)

    @property
    def unique_id(self) -> str | None:
        """Return unique ID of the entity."""
        return self._unique_id

    @property
    def icon(self) -> str | None:
        """Return icon."""
        return self._rendered.get(CONF_ICON)

    @property
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        return self._rendered.get(CONF_PICTURE)

    @property
    def available(self) -> bool:
        """Return availability of the entity."""
        return (
            self._rendered is not self._static_rendered
            and
            # Check against False so `None` is ok
            self._rendered.get(CONF_AVAILABILITY) is not False
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        return self._rendered.get(CONF_ATTRIBUTES)

    def _set_unique_id(self, unique_id: str | None) -> None:
        """Set unique id."""
        self._unique_id = unique_id

    def restore_attributes(self, last_state: State) -> None:
        """Restore attributes."""
        for conf_key, attr in CONF_TO_ATTRIBUTE.items():
            if conf_key not in self._config or attr not in last_state.attributes:
                continue
            self._rendered[conf_key] = last_state.attributes[attr]

        if CONF_ATTRIBUTES in self._config:
            extra_state_attributes = {}
            for attr in self._config[CONF_ATTRIBUTES]:
                if attr not in last_state.attributes:
                    continue
                extra_state_attributes[attr] = last_state.attributes[attr]
            self._rendered[CONF_ATTRIBUTES] = extra_state_attributes

    def _render_single_template(
        self,
        key: str,
        variables: dict[str, Any],
        strict: bool = False,
    ) -> Any:
        """Render a single template."""
        try:
            if key in self._to_render_complex:
                return render_complex(self._config[key], variables)

            return self._config[key].async_render(
                variables, parse_result=key in self._parse_result, strict=strict
            )
        except TemplateError as err:
            log_triggered_template_error(self.entity_id, err, key=key)

        return _SENTINEL

    def _render_templates(self, variables: dict[str, Any]) -> None:
        """Render templates."""
        rendered = dict(self._static_rendered)

        # Check availability first and render as a simple template because
        # availability should only be able to render True, False, or None.
        available = True
        if CONF_AVAILABILITY in self._to_render_simple:
            # Render availability with strict=True to catch template errors.
            # This is to ensure feature parity between template entities and trigger
            # based template entities.  Template entities do not go unavailable when
            # the availability template renders an error.
            if (
                result := self._render_single_template(
                    CONF_AVAILABILITY, variables, strict=True
                )
            ) is not _SENTINEL:
                rendered[CONF_AVAILABILITY] = available = result

        if not available:
            self._rendered = rendered
            return

        # If state fails to render, the entity should go unavailable.  Render the
        # state as a simple template because the result should always be a string or None.
        if CONF_STATE in self._to_render_simple:
            if (
                result := self._render_single_template(CONF_STATE, variables)
            ) is _SENTINEL:
                self._rendered = self._static_rendered
                return

            rendered[CONF_STATE] = result

        for key in itertools.chain(self._to_render_simple, self._to_render_complex):
            # Skip availability because we already handled it before.
            if key in (CONF_AVAILABILITY, CONF_STATE):
                continue

            if (
                result := self._render_single_template(
                    key, variables, strict=key in self._to_render_complex
                )
            ) is not _SENTINEL:
                rendered[key] = result

        if CONF_ATTRIBUTES in self._config:
            attributes = {}
            for attribute, attribute_template in self._config[CONF_ATTRIBUTES].items():
                try:
                    value = render_complex(attribute_template, variables)
                    attributes[attribute] = value
                    variables.update({attribute: value})
                except TemplateError as err:
                    log_triggered_template_error(
                        self.entity_id, err, attribute=attribute
                    )
            rendered[CONF_ATTRIBUTES] = attributes

        self._rendered = rendered


class ManualTriggerEntity(TriggerBaseEntity):
    """Template entity based on manual trigger data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerBaseEntity.__init__(self, hass, config)
        # Need initial rendering on `name` as it influence the `entity_id`
        self._rendered[CONF_NAME] = config[CONF_NAME].async_render(
            {},
            parse_result=CONF_NAME in self._parse_result,
        )

    @callback
    def _process_manual_data(self, value: Any | None = None) -> None:
        """Process new data manually.

        Implementing class should call this last in update method to render templates.
        Ex: self._process_manual_data(payload)
        """

        run_variables: dict[str, Any] = {"value": value}
        # Silently try if variable is a json and store result in `value_json` if it is.
        with contextlib.suppress(*JSON_DECODE_EXCEPTIONS):
            run_variables["value_json"] = json_loads(run_variables["value"])
        variables = {
            "this": TemplateStateFromEntityId(self.hass, self.entity_id),
            **(run_variables or {}),
        }

        self._render_templates(variables)


class ManualTriggerSensorEntity(ManualTriggerEntity, SensorEntity):
    """Template entity based on manual trigger data for sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> None:
        """Initialize the sensor entity."""
        ManualTriggerEntity.__init__(self, hass, config)
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_state_class = config.get(CONF_STATE_CLASS)
