"""TemplateEntity utility class."""

from __future__ import annotations

import itertools
import logging
from typing import Any

import jinja2
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
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from . import config_validation as cv
from .entity import Entity
from .template import (
    _SENTINEL,
    Template,
    TemplateStateFromEntityId,
    _render_with_context,
    render_complex,
    result_as_boolean,
)
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


class ValueTemplate(Template):
    """Class to hold a value_template and manage caching and rendering it with 'value' in variables."""

    @classmethod
    def from_template(cls, template: Template) -> ValueTemplate:
        """Create a ValueTemplate object from a Template object."""
        return cls(template.template, template.hass)

    @callback
    def async_render_as_value_template(
        self, entity_id: str, variables: dict[str, Any], error_value: Any
    ) -> Any:
        """Render template that requires 'value' and optionally 'value_json'.

        Template errors will be suppressed when an error_value is supplied.

        This method must be run in the event loop.
        """
        self._renders += 1

        if self.is_static:
            return self.template

        compiled = self._compiled or self._ensure_compiled()

        try:
            render_result = _render_with_context(
                self.template, compiled, **variables
            ).strip()
        except jinja2.TemplateError as ex:
            message = f"Error parsing value for {entity_id}: {ex} (value: {variables['value']}, template: {self.template})"
            logger = logging.getLogger(f"{__package__}.{entity_id.split('.')[0]}")
            logger.debug(message)
            return error_value

        return render_result


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

        self._availability_template = config.get(CONF_AVAILABILITY)
        self._available = True

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
        if self._availability_template is None:
            return True

        return self._available

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

    def _template_variables(self, run_variables: dict[str, Any] | None = None) -> dict:
        """Render template variables."""
        return {
            "this": TemplateStateFromEntityId(self.hass, self.entity_id),
            **(run_variables or {}),
        }

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

    def _render_availability_template(self, variables: dict[str, Any]) -> bool:
        """Render availability template."""
        if not self._availability_template:
            return True

        try:
            if (
                available := self._availability_template.async_render(
                    variables, parse_result=True, strict=True
                )
            ) is False:
                self._rendered = dict(self._static_rendered)

            self._available = result_as_boolean(available)

        except TemplateError as err:
            # The entity will be available when an error is rendered. This
            # ensures functionality is consistent between template and trigger template
            # entities.
            self._available = True
            log_triggered_template_error(self.entity_id, err, key=CONF_AVAILABILITY)

        return self._available

    def _render_attributes(self, rendered: dict, variables: dict[str, Any]) -> None:
        """Render template attributes."""
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

    def _render_single_templates(
        self,
        rendered: dict,
        variables: dict[str, Any],
        filtered: list[str] | None = None,
    ) -> None:
        """Render all single templates."""
        for key in itertools.chain(self._to_render_simple, self._to_render_complex):
            if filtered and key in filtered:
                continue

            if (
                result := self._render_single_template(key, variables)
            ) is not _SENTINEL:
                rendered[key] = result

    def _render_templates(self, variables: dict[str, Any]) -> None:
        """Render templates."""
        rendered = dict(self._static_rendered)
        self._render_single_templates(rendered, variables)
        self._render_attributes(rendered, variables)
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

    def _template_variables_with_value(
        self, value: str | None = None
    ) -> dict[str, Any]:
        """Render template variables.

        Implementing class should call this first in update method to render variables for templates.
        Ex: variables = self._render_template_variables_with_value(payload)
        """
        run_variables: dict[str, Any] = {"value": value}

        # Silently try if variable is a json and store result in `value_json` if it is.
        try:  # noqa: SIM105 - suppress is much slower
            run_variables["value_json"] = json_loads(value)  # type: ignore[arg-type]
        except JSON_DECODE_EXCEPTIONS:
            pass

        return self._template_variables(run_variables)

    @callback
    def _process_manual_data(self, variables: dict[str, Any]) -> None:
        """Process new data manually.

        Implementing class should call this last in update method to render templates.
        Ex: self._process_manual_data(variables)
        """
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
