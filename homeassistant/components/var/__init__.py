"""Allows the creation of generic variable entities."""

import logging
from typing import Union, Sequence
import asyncio
import json

import voluptuous as vol

from homeassistant.core import callback, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE,
    CONF_ICON, CONF_ICON_TEMPLATE, ATTR_ENTITY_PICTURE,
    CONF_ENTITY_PICTURE_TEMPLATE, ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_START, CONF_FRIENDLY_NAME_TEMPLATE, MATCH_ALL,
    EVENT_STATE_CHANGED,
    SERVICE_RELOAD)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.json import JSONEncoder
from homeassistant.components import recorder
from homeassistant.components.recorder.models import Events
from homeassistant.helpers.service import async_register_admin_service

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'var'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_INITIAL_VALUE = 'initial_value'
CONF_RESTORE = 'restore'
CONF_FORCE_UPDATE = 'force_update'
CONF_QUERY = 'query'
CONF_COLUMN = 'column'
CONF_TRACKED_ENTITY_ID = 'tracked_entity_id'
CONF_TRACKED_EVENT_TYPE = 'tracked_event_type'

ATTR_VALUE = 'value'

def validate_event_types(value: Union[str, Sequence]) -> Sequence[str]:
    """Validate event types."""
    if value is None:
        raise vol.Invalid('Event types can not be None')
    if isinstance(value, str):
        value = [event_type.strip() for event_type in value.split(',')]

    return [event_type for event_type in value]

def validate_sql_select(value):
    """Validate that value is a SQL SELECT query."""
    if not value.lstrip().lower().startswith('select'):
        raise vol.Invalid('Only SELECT queries allowed')
    return value

SERVICE_SET = "set"
SERVICE_SET_SCHEMA = make_entity_service_schema({
        vol.Optional(ATTR_VALUE): cv.match_all,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_QUERY): vol.All(cv.string, validate_sql_select),
        vol.Optional(CONF_COLUMN): cv.string,
        vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_RESTORE): cv.boolean,
        vol.Optional(CONF_FORCE_UPDATE): cv.boolean,
        vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(ATTR_ENTITY_PICTURE): cv.string,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_TRACKED_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_TRACKED_EVENT_TYPE): validate_event_types,
})

SERVICE_UPDATE = "update"
SERVICE_UPDATE_SCHEMA = make_entity_service_schema({})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Any({
            vol.Optional(CONF_INITIAL_VALUE): cv.match_all,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_QUERY): vol.All(cv.string, validate_sql_select),
            vol.Optional(CONF_COLUMN): cv.string,
            vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_RESTORE): cv.boolean,
            vol.Optional(CONF_FORCE_UPDATE): cv.boolean,
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_FRIENDLY_NAME_TEMPLATE): cv.template,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_ICON_TEMPLATE): cv.template,
            vol.Optional(ATTR_ENTITY_PICTURE): cv.string,
            vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
            vol.Optional(CONF_TRACKED_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_TRACKED_EVENT_TYPE): validate_event_types,
        }, None)
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    """Set up variables from config."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    if not await _load_from_config(hass, config, component):
        return False

    component.async_register_entity_service(
        SERVICE_SET, SERVICE_SET_SCHEMA,
        'async_set'
    )

    component.async_register_entity_service(
        SERVICE_UPDATE, SERVICE_UPDATE_SCHEMA,
        'async_force_update'
    )

    # reload handling
    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Reload yaml entities."""
        conf = await component.async_prepare_reload()
        if conf is None:
            conf = {DOMAIN: {}}
        await _load_from_config(hass, conf, component)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler
    )

    return True

async def _load_from_config(hass, config, component):
    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        initial_value = cfg.get(CONF_INITIAL_VALUE)
        unit = cfg.get(ATTR_UNIT_OF_MEASUREMENT)
        restore = cfg.get(CONF_RESTORE, True)
        force_update = cfg.get(CONF_FORCE_UPDATE, False) 
        friendly_name = cfg.get(ATTR_FRIENDLY_NAME, object_id)
        icon = cfg.get(CONF_ICON)
        entity_picture = cfg.get(ATTR_ENTITY_PICTURE)

        value_template = cfg.get(CONF_VALUE_TEMPLATE)
        friendly_name_template = cfg.get(CONF_FRIENDLY_NAME_TEMPLATE)
        icon_template = cfg.get(CONF_ICON_TEMPLATE)
        entity_picture_template = cfg.get(CONF_ENTITY_PICTURE_TEMPLATE)
        for template in (value_template,
           icon_template,
           entity_picture_template,
           friendly_name_template,
        ):
            if template is not None:
                template.hass = hass

        manual_entity_ids = cfg.get(CONF_TRACKED_ENTITY_ID)

        tracked_entity_ids = list()
        if manual_entity_ids is not None:
            tracked_entity_ids = list(set(manual_entity_ids))

        tracked_event_types = cfg.get(CONF_TRACKED_EVENT_TYPE)
        if tracked_event_types is not None:
            tracked_event_types = list(set(tracked_event_types))

        query = cfg.get(CONF_QUERY)
        column = cfg.get(CONF_COLUMN)

        session = hass.data[recorder.DATA_INSTANCE].get_session()

        entities.append(
            Variable(
                hass,
                object_id,
                initial_value,
                value_template,
                session,
                query,
                column,
                unit,
                restore,
                force_update,
                friendly_name,
                friendly_name_template,
                icon,
                icon_template,
                entity_picture,
                entity_picture_template,
                tracked_entity_ids,
                tracked_event_types)
            )

    if not entities:
        return False

    await component.async_add_entities(entities)
    return True

class Variable(RestoreEntity):
    """Representation of a variable."""

    def __init__(self, hass, object_id, initial_value, value_template,
                 session, query, column, unit, restore, force_update,
                 friendly_name, friendly_name_template, icon,
                 icon_template, entity_picture, entity_picture_template,
                 tracked_entity_ids, tracked_event_types):
        """Initialize a variable."""
        self.hass = hass
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._value = initial_value
        self._initial_value = initial_value
        self._value_template = value_template
        self._session = session
        if query is not None and not 'LIMIT' in query:
            self._query = query.replace(";", " LIMIT 1;")
        else:
            self._query = query
        self._column = column
        self._unit = unit
        self._restore = restore
        self._force_update = force_update
        self._friendly_name = friendly_name
        self._friendly_name_template = friendly_name_template
        self._icon = icon
        self._icon_template = icon_template
        self._entity_picture = entity_picture
        self._entity_picture_template = entity_picture_template
        self._tracked_entity_ids = tracked_entity_ids
        self._stop_track_state_change = None
        self._tracked_event_types = tracked_event_types
        self._stop_track_events = []

    def _is_event_in_db(self, event):
        """Query the database to see if the event has been written."""
        event_id = self._session.query(Events.event_id).filter_by(
            event_type=event.event_type, time_fired=event.time_fired,
            event_data=json.dumps(event.data, cls=JSONEncoder)).scalar()
        return event_id is not None

    def _get_variable_event_listener(self):
        @callback
        def listener(event):
            """Update variable once monitored event fires and is recorded to the database."""
            # Skip untracked state changes
            if (event.event_type == EVENT_STATE_CHANGED and
               self._tracked_entity_ids is not None and
               event.data['entity_id'] not in self._tracked_entity_ids):
                return

            # Schedule update immediately if there is no query
            if self._query is None:
                self.async_schedule_update_ha_state(True)
                return

            # Otherwise poll the database scheduling update once event has been committed
            async def update_var():
                """Poll the database until the event shows up."""
                while not self._is_event_in_db(event):
                    await asyncio.sleep(1)
                self.async_schedule_update_ha_state(True)

            self.hass.add_job(update_var)
        return listener

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def variable_startup(event):
            """Update variable event listeners on startup."""
            if self._tracked_entity_ids is not None:
                listener = self._get_variable_event_listener()
                stop = self.hass.bus.async_listen(EVENT_STATE_CHANGED, listener)
                self._stop_track_state_change = stop
            if self._tracked_event_types is not None:
                listener = self._get_variable_event_listener()
                for event_type in self._tracked_event_types:
                    stop = self.hass.bus.async_listen(event_type, listener)
                    self._stop_track_events.append(stop)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, variable_startup)

        # Restore previous value on startup
        await super().async_added_to_hass()
        if self._restore == True:
            state = await self.async_get_last_state()
            if state:
                self._value = state.state

    async def async_will_remove_from_hass(self):
        # Remove event listeners when the entity is removed from hass (for instance when 'reload' is triggered by user)
        if self._stop_track_state_change:
            self._stop_track_state_change()
        if self._stop_track_events:
            for stop in self._stop_track_events:
                stop()

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False
    
    @property
    def force_update(self):
        """Return True if state updates should be forced.
        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return self._force_update

    @property
    def name(self):
        """Return the name of the variable."""
        return self._friendly_name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity_picture to be used for this entity."""
        return self._entity_picture

    @property
    def state(self):
        """Return the state of the component."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def _templates_dict(self):
        return {'_value': self._value_template,
                '_name': self._friendly_name_template,
                '_icon': self._icon_template,
                '_entity_picture': self._entity_picture_template}

    async def async_set(self,
            value=None,
            value_template=None,
            query=None,
            column=None,
            unit=None,
            restore=None,
            force_update=None,
            friendly_name=None,
            friendly_name_template=None,
            icon=None,
            icon_template=None,
            entity_picture=None,
            entity_picture_template=None,
            manual_tracked_entity_ids=None,
            tracked_event_types=None):
        """Set new attributes for the variable."""
        if value is not None:
            self._value = value
        if unit is not None:
            self._unit = unit
        if restore is not None:
            self._restore = restore
        if force_update is not None:
            self._force_update = force_update
        if friendly_name is not None:
            self._friendly_name = friendly_name
        if icon is not None:
            self._icon = icon
        if entity_picture is not None:
            self._entity_picture = entity_picture
        templates_dict = {
                '_value': value_template,
                '_name': friendly_name_template,
                '_icon': icon_template,
                '_entity_picture': entity_picture_template}
        for property_name, template in templates_dict.items():
            if template is not None:
                template.hass = self.hass
                setattr(self, property_name, template.async_render())
        if query is not None:
          self._query = query
        if column is not None:
          self._column = column

        tracked_entity_ids = None
        if manual_tracked_entity_ids is not None:
            tracked_entity_ids = manual_tracked_entity_ids

        if tracked_entity_ids is not None:
            if self._stop_track_state_change:
                self._stop_track_state_change()
            self._tracked_entity_ids = tracked_entity_ids
            listener = self._get_variable_event_listener()
            stop = self.hass.bus.async_listen(EVENT_STATE_CHANGED, listener)
            self._stop_track_state_change = stop

        if tracked_event_types is not None:
            if self._stop_track_events:
                for stop in self._stop_track_events:
                  stop()
            self._tracked_event_types = tracked_event_types
            listener = self._get_variable_event_listener()
            for event_type in self._tracked_event_types:
                stop = self.hass.bus.async_listen(event_type, listener)
                self._stop_track_events.append(stop)

        await self.async_update_ha_state()

    async def async_force_update(self):
        await self.async_update_ha_state(True)

    async def async_update(self):
        """Update the state and attributes from the templates."""

        # Run the db query
        db_value = None
        if self._query is not None:
            import sqlalchemy
            try:
                result = self._session.execute(self._query)

                if not result.returns_rows or result.rowcount == 0:
                    _LOGGER.warning("%s returned no results", self._query)
                    self._state = None
                    return

                for row in result:
                    _LOGGER.debug("result = %s", row._mapping.items())
                    db_value = row._mapping[self._column]
            except sqlalchemy.exc.SQLAlchemyError as err:
                _LOGGER.error("Error executing query %s: %s", self._query, err)
                return
            finally:
                self._session.close()

        # Update the state and attributes from their templates
        for property_name, template in self._templates_dict.items():
            if property_name != '_value' and template is None:
                continue
            elif property_name == '_value' and template is None and db_value is None:
                continue

            try:
                rendered_template = None
                if template is not None:
                    if db_value is not None:
                        rendered_template = template.async_render_with_possible_json_value(db_value, None)
                    else:
                        rendered_template = template.async_render()

                if rendered_template is not None:
                    setattr(self, property_name, rendered_template)
                elif property_name == '_value' and db_value is not None:
                    setattr(self, property_name, db_value)
            except TemplateError as ex:
                friendly_property_name = property_name[1:].replace('_', ' ')
                if ex.args and ex.args[0].startswith(
                        "UndefinedError: 'None' has no attribute"):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning('Could not render %s template %s,'
                                    ' the state is unknown.',
                                    friendly_property_name, self._friendly_name)
                    continue

                try:
                    setattr(self, property_name, getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error('Could not render %s template %s: %s',
                                  friendly_property_name, self._friendly_name, ex)

