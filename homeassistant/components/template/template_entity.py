"""TemplateEntity utility class."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import dataclass
import itertools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_ICON,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import CoreState, Event, State, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    async_track_template_result,
)
from homeassistant.helpers.restore_state import (
    ExtraStoredData,
    RestoreEntity,
    RestoreStateData,
)
from homeassistant.helpers.template import Template, result_as_boolean

from . import TemplateJSONDecoder, TemplateJSONEncoder
from .const import (
    CONF_ATTRIBUTE_TEMPLATES,
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_PICTURE,
    CONF_RESTORE,
)

_LOGGER = logging.getLogger(__name__)


TEMPLATE_ENTITY_AVAILABILITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AVAILABILITY): cv.template,
    }
)

TEMPLATE_ENTITY_ICON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ICON): cv.template,
    }
)

TEMPLATE_ENTITY_RESTORE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_RESTORE): cv.boolean,
    }
)

TEMPLATE_ENTITY_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ATTRIBUTES): vol.Schema({cv.string: cv.template}),
        vol.Optional(CONF_AVAILABILITY): cv.template,
        vol.Optional(CONF_ICON): cv.template,
        vol.Optional(CONF_PICTURE): cv.template,
    }
)

TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY = vol.Schema(
    {
        vol.Optional(CONF_ATTRIBUTE_TEMPLATES, default={}): vol.Schema(
            {cv.string: cv.template}
        ),
    }
)

TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY = vol.Schema(
    {
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
    }
)

TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY = vol.Schema(
    {
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    }
).extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema)


LEGACY_FIELDS = {
    CONF_ICON_TEMPLATE: CONF_ICON,
    CONF_ENTITY_PICTURE_TEMPLATE: CONF_PICTURE,
    CONF_AVAILABILITY_TEMPLATE: CONF_AVAILABILITY,
    CONF_ATTRIBUTE_TEMPLATES: CONF_ATTRIBUTES,
    CONF_FRIENDLY_NAME: CONF_NAME,
}


def rewrite_common_legacy_to_modern_conf(
    entity_cfg: dict[str, Any], extra_legacy_fields: dict[str, str] = None
) -> dict[str, Any]:
    """Rewrite legacy config."""
    entity_cfg = {**entity_cfg}
    if extra_legacy_fields is None:
        extra_legacy_fields = {}

    for from_key, to_key in itertools.chain(
        LEGACY_FIELDS.items(), extra_legacy_fields.items()
    ):
        if from_key not in entity_cfg or to_key in entity_cfg:
            continue

        val = entity_cfg.pop(from_key)
        if isinstance(val, str):
            val = Template(val)
        entity_cfg[to_key] = val

    if CONF_NAME in entity_cfg and isinstance(entity_cfg[CONF_NAME], str):
        entity_cfg[CONF_NAME] = Template(entity_cfg[CONF_NAME])

    return entity_cfg


class _TemplateAttribute:
    """Attribute value linked to template result."""

    def __init__(
        self,
        entity: Entity,
        attribute: str,
        template: Template,
        validator: Callable[[Any], Any] = None,
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
        event: Event | None,
        template: Template,
        last_result: str | None | TemplateError,
        result: str | TemplateError,
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
            assert self.on_update
            self.on_update(None)
            return

        assert self.on_update
        self.on_update(validated)
        return


class TemplateEntity(RestoreEntity):
    """Entity that uses templates to calculate attributes."""

    _attr_available = True
    _attr_entity_picture = None
    _attr_icon = None
    _attr_should_poll = False

    def __init__(
        self,
        hass,
        *,
        availability_template=None,
        icon_template=None,
        entity_picture_template=None,
        attribute_templates=None,
        config=None,
        fallback_name=None,
        unique_id=None,
        save_additional_attributes: list[str] | None = None,
        always_save_state: bool = False,
    ):
        """Template Entity."""
        self._template_attrs: dict = {}
        self._async_update: Callable | None = None
        self._attr_extra_state_attributes = {}
        self._self_ref_update_count = 0
        self._attr_unique_id = unique_id
        self._save_extra_data: bool = True
        self._extra_save_data: list = save_additional_attributes or []
        self._always_save_state = always_save_state

        if config is None:
            self._attribute_templates = attribute_templates
            self._availability_template = availability_template
            self._icon_template = icon_template
            self._entity_picture_template = entity_picture_template
            self._friendly_name_template = None
            self.restore = False
        else:
            self._attribute_templates = config.get(CONF_ATTRIBUTES)
            self._availability_template = config.get(CONF_AVAILABILITY)
            self._icon_template = config.get(CONF_ICON)
            self._entity_picture_template = config.get(CONF_PICTURE)
            self._friendly_name_template = config.get(CONF_NAME)
            self.restore = config.get(CONF_RESTORE)

        # Try to render the name as it can influence the entity ID
        self._attr_name = fallback_name
        if self._friendly_name_template:
            self._friendly_name_template.hass = hass
            with contextlib.suppress(TemplateError):
                self._attr_name = self._friendly_name_template.async_render(
                    parse_result=False
                )

        # Templates will not render while the entity is unavailable, try to render the
        # icon and picture templates.
        if self._entity_picture_template:
            self._entity_picture_template.hass = hass
            with contextlib.suppress(TemplateError):
                self._attr_entity_picture = self._entity_picture_template.async_render(
                    parse_result=False
                )

        if self._icon_template:
            self._icon_template.hass = hass
            with contextlib.suppress(TemplateError):
                self._attr_icon = self._icon_template.async_render(parse_result=False)

    @property
    def save_extra_data(self) -> bool:
        """Return if extra attributes data is to be saved or not."""
        return self._save_extra_data

    @callback
    def _update_available(self, result):
        if isinstance(result, TemplateError):
            self._attr_available = True
            return

        self._attr_available = result_as_boolean(result)

    @callback
    def _update_state(self, result):
        if self._availability_template:
            return

        self._attr_available = not isinstance(result, TemplateError)

    @callback
    def _add_attribute_template(self, attribute_key, attribute_template):
        """Create a template tracker for the attribute."""

        def _update_attribute(result):
            attr_result = None if isinstance(result, TemplateError) else result
            self._attr_extra_state_attributes[attribute_key] = attr_result

        self.add_template_attribute(
            attribute_key, attribute_template, None, _update_attribute, False, False
        )

    async def async_internal_added_to_hass(self) -> None:
        """Register this entity as a restorable entity."""
        _, data = await asyncio.gather(
            super().async_internal_added_to_hass(),
            RestoreStateData.async_get_instance(self.hass),
        )
        if not self.restore and not self._always_save_state:
            # Remove this entity for saving state and remove from
            # last_states if entity does not need to be restored
            # nor does its state always have to be saved irrespective
            # of restore.
            data.entities.pop(self.entity_id, None)
            data.last_states.pop(self.entity_id, None)

    def add_template_attribute(
        self,
        attribute: str,
        template: Template,
        validator: Callable[[Any], Any] = None,
        on_update: Callable[[Any], None] | None = None,
        none_on_template_error: bool = False,
        save_attribute: bool = True,
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
        assert self.hass is not None, "hass cannot be None"
        template.hass = self.hass
        template_attribute = _TemplateAttribute(
            self, attribute, template, validator, on_update, none_on_template_error
        )
        self._template_attrs.setdefault(template, [])
        self._template_attrs[template].append(template_attribute)
        if save_attribute and not template.is_static:
            self._extra_save_data.append(attribute)

    @callback
    def _handle_results(
        self,
        event: Event | None,
        updates: list[TrackTemplateResult],
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
        template_var_tups: list[TrackTemplate] = []
        has_availability_template = False
        for template, attributes in self._template_attrs.items():
            template_var_tup = TrackTemplate(template, None)
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

    def _add_all_template_attributes(self) -> None:
        """Add the additional template attributes."""
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

    async def restore_entity(
        self,
    ) -> tuple[State | None, dict[str, Any] | None]:
        """Restore the entity."""

        if not self.restore:
            _LOGGER.debug("Not restoring entity %s", self.entity_id)
            return None, None

        if (last_sensor_state := await self.async_get_last_state()) is None:
            _LOGGER.debug("No state found to restore for entity %s", self.entity_id)
            return None, None

        # Restore all attributes.
        _LOGGER.debug("Restoring entity %s", self.entity_id)

        # Restore any attributes.
        if self._attribute_templates is not None:
            for key in self._attribute_templates:
                try:
                    value = last_sensor_state.attributes[key]
                except KeyError:
                    _LOGGER.debug(
                        "No value stored for attribute %s for entity %s",
                        key,
                        self.entity_id,
                    )
                    continue

                self._attr_extra_state_attributes.update(
                    {key: last_sensor_state.attributes[key]}
                )
                _LOGGER.debug(
                    "Restored attribute %s for entity %s to value %s",
                    key,
                    self.entity_id,
                    value,
                )

        # Restore extra data
        if (last_sensor_data := await self.async_get_last_template_data()) is None:
            _LOGGER.debug(
                "No extra data found to restore for entity %s", self.entity_id
            )
            return last_sensor_state, None

        for attribute in self._extra_save_data:
            try:
                value = last_sensor_data[attribute]
            except KeyError:
                _LOGGER.debug(
                    "No value stored for additional attribute %s for entity %s",
                    attribute,
                    self.entity_id,
                )
                continue

            setattr(self, attribute, value)
            _LOGGER.debug(
                "Additional attribute %s restored to value %s for entity %s",
                attribute,
                value,
                self.entity_id,
            )

        self.async_write_ha_state()

        return (last_sensor_state, last_sensor_data)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        self._add_all_template_attributes()

        await self.restore_entity()

        if self.hass.state == CoreState.running:
            await self._async_template_startup()
            return

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self._async_template_startup
        )

    async def async_update(self) -> None:
        """Call for forced update."""
        if self._async_update is not None:
            self._async_update()

    def async_write_ha_state(self) -> None:
        """Write state to state machine.

        Disable saving state and re-enable again after writing state.
        If there is any uncaught error due to faulty attribute we thus
        ensure that this faulty attribute will not be saved.
        """

        try:
            self._save_extra_data = False
            super().async_write_ha_state()
            self._save_extra_data = True
        except (TypeError, ValueError) as exc:
            # Writing state resulted in an issue. Stop storing states for now.
            self._save_extra_data = False
            _LOGGER.error(
                "Writing state to state machine for entity %s results in exception: %s",
                self.entity_id,
                exc,
            )

    @property
    def extra_restore_state_data(self) -> TemplateExtraStoredData | None:
        """Return sensor specific state data for persistent saving."""
        return TemplateExtraStoredData(self, self._extra_save_data)

    async def async_get_last_template_data(self) -> dict[str, Any] | None:
        """Return the persistent saved data."""

        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return TemplateExtraStoredData(self, []).from_dict(
            restored_last_extra_data.as_dict()
        )


@dataclass
class TemplateExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    template_entity: TemplateEntity
    additional_data: list[str]

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the sensor data."""
        if not self.template_entity.save_extra_data:
            # Only store not to restore data
            _LOGGER.debug(
                "Storing of data disabled for entity %s",
                self.template_entity.entity_id,
            )
            return {}

        store_attributes: dict[str, Any] = {}
        for attribute in self.additional_data:
            try:
                value = TemplateJSONEncoder().default(
                    getattr(self.template_entity, attribute)
                )
            except AttributeError:
                continue

            _LOGGER.info(
                "Storing additional attribute %s with value %s for entity %s",
                attribute,
                value,
                self.template_entity.entity_id,
            )
            store_attributes.update({attribute: value})

        return store_attributes

    def from_dict(self, restored: dict[str, Any]) -> dict[str, Any]:
        """Initialize a stored sensor state from a dict."""
        store_attributes: dict[str, Any] = {}
        for attribute, value in restored.items():
            value = TemplateJSONDecoder().default(value)

            _LOGGER.info(
                "Retrieved additional attribute %s with value %s for entity %s",
                attribute,
                value,
                self.template_entity.entity_id,
            )
            store_attributes.update({attribute: value})

        return store_attributes
