"""TemplateEntity utility class."""

import logging
from typing import Any, Callable, List, Optional, Union

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import EVENT_HOMEASSISTANT_START, CoreState, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    Event,
    TrackTemplate,
    TrackTemplateResult,
    async_track_template_result,
)
from homeassistant.helpers.template import Template, result_as_boolean

_LOGGER = logging.getLogger(__name__)


class _TemplateAttribute:
    """Attribute value linked to template result."""

    def __init__(
        self,
        entity: Entity,
        attribute: str,
        template: Template,
        validator: Callable[[Any], Any] = None,
        on_update: Optional[Callable[[Any], None]] = None,
        none_on_template_error: Optional[bool] = False,
    ):
        """Template attribute."""
        self._entity = entity
        self._attribute = attribute
        self.template = template
        self.validator = validator
        self.on_update = on_update
        self.async_update = None
        self.none_on_template_error = none_on_template_error

    @callback
    def async_setup(self):
        """Config update path for the attribute."""
        if self.on_update:
            return

        if not hasattr(self._entity, self._attribute):
            raise AttributeError(f"Attribute '{self._attribute}' does not exist.")

        self.on_update = self._default_update

    @callback
    def _default_update(self, result):
        attr_result = None if isinstance(result, TemplateError) else result
        setattr(self._entity, self._attribute, attr_result)

    @callback
    def handle_result(
        self,
        event: Optional[Event],
        template: Template,
        last_result: Union[str, None, TemplateError],
        result: Union[str, TemplateError],
    ) -> None:
        """Handle a template result event callback."""
        if isinstance(result, TemplateError):
            _LOGGER.error(
                "TemplateError('%s') "
                "while processing template '%s' "
                "for attribute '%s' in entity '%s'",
                result,
                self.template,
                self._attribute,
                self._entity.entity_id,
            )
            if self.none_on_template_error:
                self._default_update(result)
            else:
                self.on_update(result)
            return

        if not self.validator:
            self.on_update(result)
            return

        try:
            validated = self.validator(result)
        except vol.Invalid as ex:
            _LOGGER.error(
                "Error validating template result '%s' "
                "from template '%s' "
                "for attribute '%s' in entity %s "
                "validation message '%s'",
                result,
                self.template,
                self._attribute,
                self._entity.entity_id,
                ex.msg,
            )
            self.on_update(None)
            return

        self.on_update(validated)
        return


class TemplateEntity(Entity):
    """Entity that uses templates to calculate attributes."""

    def __init__(
        self,
        *,
        availability_template=None,
        icon_template=None,
        entity_picture_template=None,
        attribute_templates=None,
    ):
        """Template Entity."""
        self._template_attrs = {}
        self._async_update = None
        self._attribute_templates = attribute_templates
        self._attributes = {}
        self._availability_template = availability_template
        self._available = True
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._icon = None
        self._entity_picture = None
        self._self_ref_update_count = 0

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @callback
    def _update_available(self, result):
        if isinstance(result, TemplateError):
            self._available = True
            return

        self._available = result_as_boolean(result)

    @callback
    def _update_state(self, result):
        if self._availability_template:
            return

        self._available = not isinstance(result, TemplateError)

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity_picture to use in the frontend, if any."""
        return self._entity_picture

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @callback
    def _add_attribute_template(self, attribute_key, attribute_template):
        """Create a template tracker for the attribute."""

        def _update_attribute(result):
            attr_result = None if isinstance(result, TemplateError) else result
            self._attributes[attribute_key] = attr_result

        self.add_template_attribute(
            attribute_key, attribute_template, None, _update_attribute
        )

    def add_template_attribute(
        self,
        attribute: str,
        template: Template,
        validator: Callable[[Any], Any] = None,
        on_update: Optional[Callable[[Any], None]] = None,
        none_on_template_error: bool = False,
    ) -> None:
        """
        Call in the constructor to add a template linked to a attribute.

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

        """
        attribute = _TemplateAttribute(
            self, attribute, template, validator, on_update, none_on_template_error
        )
        self._template_attrs.setdefault(template, [])
        self._template_attrs[template].append(attribute)

    @callback
    def _handle_results(
        self,
        event: Optional[Event],
        updates: List[TrackTemplateResult],
    ) -> None:
        """Call back the results to the attributes."""

        if event:
            self.async_set_context(event.context)

        entity_id = event and event.data.get(ATTR_ENTITY_ID)

        if entity_id and entity_id == self.entity_id:
            self._self_ref_update_count += 1
        else:
            self._self_ref_update_count = 0

        if self._self_ref_update_count > len(self._template_attrs):
            for update in updates:
                _LOGGER.warning(
                    "Template loop detected while processing event: %s, skipping template render for Template[%s]",
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

    async def _async_template_startup(self, *_) -> None:
        template_var_tups = []
        for template, attributes in self._template_attrs.items():
            template_var_tups.append(TrackTemplate(template, None))
            for attribute in attributes:
                attribute.async_setup()

        result_info = async_track_template_result(
            self.hass, template_var_tups, self._handle_results
        )
        self.async_on_remove(result_info.async_remove)
        self._async_update = result_info.async_refresh
        result_info.async_refresh()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        if self._availability_template is not None:
            self.add_template_attribute(
                "_available", self._availability_template, None, self._update_available
            )
        if self._attribute_templates is not None:
            for key, value in self._attribute_templates.items():
                self._add_attribute_template(key, value)
        if self._icon_template is not None:
            self.add_template_attribute(
                "_icon", self._icon_template, vol.Or(cv.whitespace, cv.icon)
            )
        if self._entity_picture_template is not None:
            self.add_template_attribute(
                "_entity_picture", self._entity_picture_template
            )
        if self.hass.state == CoreState.running:
            await self._async_template_startup()
            return

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self._async_template_startup
        )

    async def async_update(self) -> None:
        """Call for forced update."""
        self._async_update()
