"""TemplateEntity utility class."""
from __future__ import annotations

from collections.abc import Callable
import contextlib
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
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, CoreState, HomeAssistant, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from . import config_validation as cv
from .entity import Entity
from .event import (
    EventStateChangedData,
    TrackTemplate,
    TrackTemplateResult,
    async_track_template_result,
)
from .script import Script, _VarsType
from .template import (
    Template,
    TemplateStateFromEntityId,
    attach as template_attach,
    render_complex,
    result_as_boolean,
)
from .typing import ConfigType, EventType

_LOGGER = logging.getLogger(__name__)

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


TEMPLATE_SENSOR_BASE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
).extend(TEMPLATE_ENTITY_BASE_SCHEMA.schema)


class _TemplateAttribute:
    """Attribute value linked to template result."""

    def __init__(
        self,
        entity: Entity,
        attribute: str,
        template: Template,
        validator: Callable[[Any], Any] | None = None,
        on_update: Callable[[Any], None] | None = None,
        none_on_template_error: bool | None = False,
    ) -> None:
        """Template attribute."""
        self._entity = entity
        self._attribute = attribute
        self.template = template
        self.validator = validator
        self.on_update = on_update
        self.async_update = None
        self.none_on_template_error = none_on_template_error

    @callback
    def async_setup(self) -> None:
        """Config update path for the attribute."""
        if self.on_update:
            return

        if not hasattr(self._entity, self._attribute):
            raise AttributeError(f"Attribute '{self._attribute}' does not exist.")

        self.on_update = self._default_update

    @callback
    def _default_update(self, result: str | TemplateError) -> None:
        attr_result = None if isinstance(result, TemplateError) else result
        setattr(self._entity, self._attribute, attr_result)

    @callback
    def handle_result(
        self,
        event: EventType[EventStateChangedData] | None,
        template: Template,
        last_result: str | None | TemplateError,
        result: str | TemplateError,
    ) -> None:
        """Handle a template result event callback."""
        if isinstance(result, TemplateError):
            _LOGGER.error(
                (
                    "TemplateError('%s') "
                    "while processing template '%s' "
                    "for attribute '%s' in entity '%s'"
                ),
                result,
                self.template,
                self._attribute,
                self._entity.entity_id,
            )
            if self.none_on_template_error:
                self._default_update(result)
            else:
                assert self.on_update
                self.on_update(result)
            return

        if not self.validator:
            assert self.on_update
            self.on_update(result)
            return

        try:
            validated = self.validator(result)
        except vol.Invalid as ex:
            _LOGGER.error(
                (
                    "Error validating template result '%s' "
                    "from template '%s' "
                    "for attribute '%s' in entity %s "
                    "validation message '%s'"
                ),
                result,
                self.template,
                self._attribute,
                self._entity.entity_id,
                ex.msg,
            )
            assert self.on_update
            self.on_update(None)
            return

        assert self.on_update
        self.on_update(validated)
        return


class TemplateEntity(Entity):
    """Entity that uses templates to calculate attributes."""

    _attr_available = True
    _attr_entity_picture = None
    _attr_icon = None

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        availability_template: Template | None = None,
        icon_template: Template | None = None,
        entity_picture_template: Template | None = None,
        attribute_templates: dict[str, Template] | None = None,
        config: ConfigType | None = None,
        fallback_name: str | None = None,
        unique_id: str | None = None,
    ) -> None:
        """Template Entity."""
        self._template_attrs: dict[Template, list[_TemplateAttribute]] = {}
        self._async_update: Callable[[], None] | None = None
        self._attr_extra_state_attributes = {}
        self._self_ref_update_count = 0
        self._attr_unique_id = unique_id
        if config is None:
            self._attribute_templates = attribute_templates
            self._availability_template = availability_template
            self._icon_template = icon_template
            self._entity_picture_template = entity_picture_template
            self._friendly_name_template = None
        else:
            self._attribute_templates = config.get(CONF_ATTRIBUTES)
            self._availability_template = config.get(CONF_AVAILABILITY)
            self._icon_template = config.get(CONF_ICON)
            self._entity_picture_template = config.get(CONF_PICTURE)
            self._friendly_name_template = config.get(CONF_NAME)

        class DummyState(State):
            """None-state for template entities not yet added to the state machine."""

            def __init__(self) -> None:
                """Initialize a new state."""
                super().__init__("unknown.unknown", STATE_UNKNOWN)
                self.entity_id = None  # type: ignore[assignment]

            @property
            def name(self) -> str:
                """Name of this state."""
                return "<None>"

        variables = {"this": DummyState()}

        # Try to render the name as it can influence the entity ID
        self._attr_name = fallback_name
        if self._friendly_name_template:
            self._friendly_name_template.hass = hass
            with contextlib.suppress(TemplateError):
                self._attr_name = self._friendly_name_template.async_render(
                    variables=variables, parse_result=False
                )

        # Templates will not render while the entity is unavailable, try to render the
        # icon and picture templates.
        if self._entity_picture_template:
            self._entity_picture_template.hass = hass
            with contextlib.suppress(TemplateError):
                self._attr_entity_picture = self._entity_picture_template.async_render(
                    variables=variables, parse_result=False
                )

        if self._icon_template:
            self._icon_template.hass = hass
            with contextlib.suppress(TemplateError):
                self._attr_icon = self._icon_template.async_render(
                    variables=variables, parse_result=False
                )

    @callback
    def _update_available(self, result: str | TemplateError) -> None:
        if isinstance(result, TemplateError):
            self._attr_available = True
            return

        self._attr_available = result_as_boolean(result)

    @callback
    def _update_state(self, result: str | TemplateError) -> None:
        if self._availability_template:
            return

        self._attr_available = not isinstance(result, TemplateError)

    @callback
    def _add_attribute_template(
        self, attribute_key: str, attribute_template: Template
    ) -> None:
        """Create a template tracker for the attribute."""

        def _update_attribute(result: str | TemplateError) -> None:
            attr_result = None if isinstance(result, TemplateError) else result
            self._attr_extra_state_attributes[attribute_key] = attr_result

        self.add_template_attribute(
            attribute_key, attribute_template, None, _update_attribute
        )

    def add_template_attribute(
        self,
        attribute: str,
        template: Template,
        validator: Callable[[Any], Any] | None = None,
        on_update: Callable[[Any], None] | None = None,
        none_on_template_error: bool = False,
    ) -> None:
        """Call in the constructor to add a template linked to a attribute.

        Parameters
        ----------
        attribute
            The name of the attribute to link to. This attribute must exist
            unless a custom on_update method is supplied.
        template
            The template to calculate.
        validator
            Validator function to parse the result and ensure it's valid.
        on_update
            Called to store the template result rather than storing it
            the supplied attribute. Passed the result of the validator, or None
            if the template or validator resulted in an error.
        none_on_template_error
            If True, the attribute will be set to None if the template errors.

        """
        assert self.hass is not None, "hass cannot be None"
        template.hass = self.hass
        template_attribute = _TemplateAttribute(
            self, attribute, template, validator, on_update, none_on_template_error
        )
        self._template_attrs.setdefault(template, [])
        self._template_attrs[template].append(template_attribute)

    @callback
    def _handle_results(
        self,
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        """Call back the results to the attributes."""
        if event:
            self.async_set_context(event.context)

        entity_id = event and event.data["entity_id"]

        if entity_id and entity_id == self.entity_id:
            self._self_ref_update_count += 1
        else:
            self._self_ref_update_count = 0

        if self._self_ref_update_count > len(self._template_attrs):
            for update in updates:
                _LOGGER.warning(
                    (
                        "Template loop detected while processing event: %s, skipping"
                        " template render for Template[%s]"
                    ),
                    event,
                    update.template.template,
                )
            return

        for update in updates:
            for attr in self._template_attrs[update.template]:
                attr.handle_result(
                    event, update.template, update.last_result, update.result
                )

        self.async_write_ha_state()

    async def _async_template_startup(self, *_: Any) -> None:
        template_var_tups: list[TrackTemplate] = []
        has_availability_template = False

        variables = {"this": TemplateStateFromEntityId(self.hass, self.entity_id)}

        for template, attributes in self._template_attrs.items():
            template_var_tup = TrackTemplate(template, variables)
            is_availability_template = False
            for attribute in attributes:
                # pylint: disable-next=protected-access
                if attribute._attribute == "_attr_available":
                    has_availability_template = True
                    is_availability_template = True
                attribute.async_setup()
            # Insert the availability template first in the list
            if is_availability_template:
                template_var_tups.insert(0, template_var_tup)
            else:
                template_var_tups.append(template_var_tup)

        result_info = async_track_template_result(
            self.hass,
            template_var_tups,
            self._handle_results,
            has_super_template=has_availability_template,
        )
        self.async_on_remove(result_info.async_remove)
        self._async_update = result_info.async_refresh
        result_info.async_refresh()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        if self._availability_template is not None:
            self.add_template_attribute(
                "_attr_available",
                self._availability_template,
                None,
                self._update_available,
            )
        if self._attribute_templates is not None:
            for key, value in self._attribute_templates.items():
                self._add_attribute_template(key, value)
        if self._icon_template is not None:
            self.add_template_attribute(
                "_attr_icon", self._icon_template, vol.Or(cv.whitespace, cv.icon)
            )
        if self._entity_picture_template is not None:
            self.add_template_attribute(
                "_attr_entity_picture", self._entity_picture_template
            )
        if (
            self._friendly_name_template is not None
            and not self._friendly_name_template.is_static
        ):
            self.add_template_attribute("_attr_name", self._friendly_name_template)

        if self.hass.state == CoreState.running:
            await self._async_template_startup()
            return

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self._async_template_startup
        )

    async def async_update(self) -> None:
        """Call for forced update."""
        assert self._async_update
        self._async_update()

    async def async_run_script(
        self,
        script: Script,
        *,
        run_variables: _VarsType | None = None,
        context: Context | None = None,
    ) -> None:
        """Run an action script."""
        if run_variables is None:
            run_variables = {}
        await script.async_run(
            run_variables={
                "this": TemplateStateFromEntityId(self.hass, self.entity_id),
                **run_variables,
            },
            context=context,
        )


class TemplateSensor(TemplateEntity, SensorEntity):
    """Representation of a Template Sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config: dict[str, Any],
        fallback_name: str | None,
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            hass, config=config, fallback_name=fallback_name, unique_id=unique_id
        )

        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_state_class = config.get(CONF_STATE_CLASS)


class TriggerBaseEntity(Entity):
    """Template Base entity based on trigger data."""

    domain: str
    extra_template_keys: tuple | None = None
    extra_template_keys_complex: tuple | None = None
    _unique_id: str | None

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        self.hass = hass

        self._set_unique_id(config.get(CONF_UNIQUE_ID))

        self._config = config

        self._static_rendered = {}
        self._to_render_simple = []
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

    @property
    def name(self) -> str | None:
        """Name of the entity."""
        return self._rendered.get(CONF_NAME)

    @property
    def unique_id(self) -> str | None:
        """Return unique ID of the entity."""
        return self._unique_id

    @property
    def device_class(self):  # type: ignore[no-untyped-def]
        """Return device class of the entity."""
        return self._config.get(CONF_DEVICE_CLASS)

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

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        template_attach(self.hass, self._config)

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

    def _render_templates(self, variables: dict[str, Any]) -> None:
        """Render templates."""
        try:
            rendered = dict(self._static_rendered)

            for key in self._to_render_simple:
                rendered[key] = self._config[key].async_render(
                    variables,
                    parse_result=key in self._parse_result,
                )

            for key in self._to_render_complex:
                rendered[key] = render_complex(
                    self._config[key],
                    variables,
                )

            if CONF_ATTRIBUTES in self._config:
                rendered[CONF_ATTRIBUTES] = render_complex(
                    self._config[CONF_ATTRIBUTES],
                    variables,
                )

            self._rendered = rendered
        except TemplateError as err:
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").error(
                "Error rendering %s template for %s: %s", key, self.entity_id, err
            )
            self._rendered = self._static_rendered


class ManualTriggerEntity(TriggerBaseEntity):
    """Template entity based on manual trigger data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
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

        self.async_write_ha_state()
        this = None
        if state := self.hass.states.get(self.entity_id):
            this = state.as_dict()

        run_variables: dict[str, Any] = {"value": value}
        # Silently try if variable is a json and store result in `value_json` if it is.
        with contextlib.suppress(*JSON_DECODE_EXCEPTIONS):
            run_variables["value_json"] = json_loads(run_variables["value"])
        variables = {"this": this, **(run_variables or {})}

        self._render_templates(variables)
