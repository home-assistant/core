"""TemplateEntity utility class."""

import logging
from typing import Optional, Callable, Any, Union

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import match_all
from homeassistant.helpers.event import async_track_template_result, Event
from homeassistant.helpers.template import Template

_LOGGER = logging.getLogger(__name__)


class _TemplateAttribute:
    """Attribute value linked to template result."""

    def __init__(
            self,
            entity: Entity,
            attribute: str,
            template: Template,
            validator: Callable[[Any], Any] = match_all,
            on_update: Optional[Callable[[Any], None]] = None):
        """Initialiser."""
        self._entity = entity
        self._attribute = attribute
        self.template = template
        self.validator = validator
        if on_update is None:
            if not hasattr(entity, attribute):
                raise AttributeError(
                    "Attribute '{}' does not exist.".format(attribute))

            def _default_update(result):
                setattr(entity, attribute, result)
                entity.async_schedule_update_ha_state()
            self.on_update = _default_update
        else:
            self.on_update = on_update
        self.async_update = match_all
        self.async_will_remove_from_hass = match_all

    @callback
    def _handle_result(
            self,
            event: Optional[Event],
            template: Template,
            last_result: Optional[str],
            result: Union[str, TemplateError]) -> None:
        if isinstance(result, TemplateError):
            _LOGGER.error(
                "TemplateError('%s') "
                "while processing template '%s' "
                "for attribute '%s' in entity '%s'",
                result,
                self.template,
                self._attribute,
                self._entity.entity_id)
            self.on_update(None)
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
                ex.msg)
            self.on_update(None)
            return

        self.on_update(validated)

    @callback
    def async_added_to_hass(self) -> None:
        """Call from containing entity when added to hass."""
        result_info = async_track_template_result(
            self._entity.hass,
            self.template,
            self._handle_result
        )
        self.async_will_remove_from_hass = result_info.async_remove
        self.async_update = result_info.async_refresh


class TemplateEntity(Entity):
    """Entity that uses templates to calculate attributes."""

    def __init__(self):
        """Initialiser."""
        self._template_attrs = []

    def add_template_attribute(
            self,
            attribute: str,
            template: Template,
            validator: Callable[[Any], Any] = match_all,
            on_update: Optional[Callable[[Any], None]] = None) -> None:
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
        self._template_attrs.append(_TemplateAttribute(
            self, attribute, template, validator, on_update))

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        for attribute in self._template_attrs:
            attribute.async_added_to_hass()

    async def async_update(self) -> None:
        """Call for forced update."""
        for attribute in self._template_attrs:
            attribute.async_update()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for attribute in self._template_attrs:
            attribute.async_will_remove_from_hass()
