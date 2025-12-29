"""TemplateEntity utility class."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import contextlib
import logging
from typing import Any, cast

from propcache.api import under_cached_property
import voluptuous as vol

from homeassistant.components.blueprint import CONF_USE_BLUEPRINT
from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_PATH,
    CONF_VARIABLES,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
    validate_state,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    async_track_template_result,
)
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.template import (
    Template,
    TemplateStateFromEntityId,
    result_as_boolean,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ATTRIBUTES, CONF_AVAILABILITY, CONF_PICTURE
from .entity import AbstractTemplateEntity

_LOGGER = logging.getLogger(__name__)


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
        event: Event[EventStateChangedData] | None,
        template: Template,
        last_result: str | TemplateError | None,
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


class TemplateEntity(AbstractTemplateEntity):
    """Entity that uses templates to calculate attributes."""

    _attr_available = True
    _attr_entity_picture = None
    _attr_icon = None

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Template Entity."""
        AbstractTemplateEntity.__init__(self, hass, config)
        self._template_attrs: dict[Template, list[_TemplateAttribute]] = {}
        self._template_result_info: TrackTemplateResultInfo | None = None
        self._attr_extra_state_attributes = {}
        self._self_ref_update_count = 0
        self._attr_unique_id = unique_id
        self._preview_callback: (
            Callable[
                [
                    str | None,
                    dict[str, Any] | None,
                    dict[str, bool | set[str]] | None,
                    str | None,
                ],
                None,
            ]
            | None
        ) = None
        self._run_variables: ScriptVariables | dict
        self._attribute_templates = config.get(CONF_ATTRIBUTES)
        self._availability_template = config.get(CONF_AVAILABILITY)
        self._run_variables = config.get(CONF_VARIABLES, {})
        self._blueprint_inputs = config.get("raw_blueprint_inputs")

        class DummyState(State):
            """None-state for template entities not yet added to the state machine."""

            def __init__(self) -> None:
                """Initialize a new state."""
                super().__init__("unknown.unknown", STATE_UNKNOWN)
                self.entity_id = None  # type: ignore[assignment]

            @under_cached_property
            def name(self) -> str:
                """Name of this state."""
                return "<None>"

        # Render the current variables and add a dummy this variable to them.
        variables = (
            self._run_variables
            if isinstance(self._run_variables, dict)
            else self._run_variables.async_render(self.hass, {})
        )
        variables = {"this": DummyState(), **variables}

        self.add_template(
            CONF_AVAILABILITY, "_attr_available", on_update=self._update_available
        )

        # Render name, icon, and picture early. name is rendered early because it influences
        # the entity_id.  icon and picture are rendered early to ensure they are populated even
        # if the entity renders unavailable.
        self._attr_name = None
        for option, attribute, validator in (
            (CONF_ICON, "_attr_icon", vol.Or(cv.whitespace, cv.icon)),
            (CONF_PICTURE, "_attr_entity_picture", cv.string),
            (CONF_NAME, "_attr_name", cv.string),
        ):
            if template := self.add_template(
                option, attribute, validator, add_if_static=option != CONF_NAME
            ):
                with contextlib.suppress(TemplateError):
                    setattr(
                        self,
                        attribute,
                        template.async_render(variables=variables, parse_result=False),
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

    @property
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        if self._blueprint_inputs is None:
            return None
        return cast(str, self._blueprint_inputs[CONF_USE_BLUEPRINT][CONF_PATH])

    def _render_script_variables(self) -> dict[str, Any]:
        """Render configured variables."""
        if isinstance(self._run_variables, dict):
            return self._run_variables

        return self._run_variables.async_render(
            self.hass,
            {
                "this": TemplateStateFromEntityId(self.hass, self.entity_id),
            },
        )

    def setup_state_template(
        self,
        option: str,
        attribute: str,
        validator: Callable[[Any], Any] | None = None,
        on_update: Callable[[Any], None] | None = None,
    ) -> None:
        """Set up a template that manages the main state of the entity."""

        @callback
        def _update_state(result: Any) -> None:
            if isinstance(result, TemplateError):
                setattr(self, attribute, None)
                if self._availability_template:
                    return

                self._attr_available = False
                return

            state = validator(result) if validator else result
            if on_update:
                on_update(state)
            else:
                setattr(self, attribute, state)

        self.add_template(option, attribute, on_update=_update_state)

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
        if self.hass is None:
            raise ValueError("hass cannot be None")
        if template.hass is None:
            raise ValueError("template.hass cannot be None")
        template_attribute = _TemplateAttribute(
            self, attribute, template, validator, on_update, none_on_template_error
        )
        self._template_attrs.setdefault(template, [])
        self._template_attrs[template].append(template_attribute)

    @callback
    def _handle_results(
        self,
        event: Event[EventStateChangedData] | None,
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

        errors = []
        for update in updates:
            for template_attr in self._template_attrs[update.template]:
                template_attr.handle_result(
                    event, update.template, update.last_result, update.result
                )
                if isinstance(update.result, TemplateError):
                    errors.append(update.result)

        if not self._preview_callback:
            self.async_write_ha_state()
            return

        if errors:
            self._preview_callback(None, None, None, str(errors[-1]))
            return

        try:
            calculated_state = self._async_calculate_state()
            validate_state(calculated_state.state)
        except Exception as err:  # noqa: BLE001
            self._preview_callback(None, None, None, str(err))
        else:
            assert self._template_result_info
            self._preview_callback(
                calculated_state.state,
                calculated_state.attributes,
                self._template_result_info.listeners,
                None,
            )

    @callback
    def _async_template_startup(
        self,
        _hass: HomeAssistant | None,
        log_fn: Callable[[int, str], None] | None = None,
    ) -> None:
        template_var_tups: list[TrackTemplate] = []
        has_availability_template = False

        variables = {
            "this": TemplateStateFromEntityId(self.hass, self.entity_id),
            **self._render_script_variables(),
        }

        for template, attributes in self._template_attrs.items():
            template_var_tup = TrackTemplate(template, variables)
            is_availability_template = False
            for attribute in attributes:
                if attribute._attribute == "_attr_available":  # noqa: SLF001
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
            log_fn=log_fn,
            has_super_template=has_availability_template,
        )
        self.async_on_remove(result_info.async_remove)
        self._template_result_info = result_info
        result_info.async_refresh()

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""

        # Handle attributes as a dictionary.
        if self._attribute_templates is not None:
            for key, value in self._attribute_templates.items():
                self._add_attribute_template(key, value)

        # Iterate all dynamic templates and add listeners.
        for entity_template in self._templates.values():
            self.add_template_attribute(
                entity_template.attribute,
                entity_template.template,
                entity_template.validator,
                entity_template.on_update,
                entity_template.none_on_template_error,
            )

    @callback
    def async_start_preview(
        self,
        preview_callback: Callable[
            [
                str | None,
                Mapping[str, Any] | None,
                dict[str, bool | set[str]] | None,
                str | None,
            ],
            None,
        ],
    ) -> CALLBACK_TYPE:
        """Render a preview."""

        def suppress_preview_errors(level: int, msg: str) -> None:
            """Suppress redundant template render errors.

            Preview entities render templates at least 3 times before the preview entity
            is created. If template contains an error, each render will produce an error.
            Instead of overwhelming the client with errors, suppress them and raise
            a single error through the self._handle_results method.
            """

        self._preview_callback = preview_callback
        self._async_setup_templates()
        try:
            self._async_template_startup(None, suppress_preview_errors)
        except Exception as err:  # noqa: BLE001
            preview_callback(None, None, None, str(err))
        return self._call_on_remove_callbacks

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._async_setup_templates()

        async_at_start(self.hass, self._async_template_startup)

    async def async_update(self) -> None:
        """Call for forced update."""
        assert self._template_result_info
        self._template_result_info.async_refresh()
