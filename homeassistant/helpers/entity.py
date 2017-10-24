"""An abstract class for entities."""
import asyncio
import logging
import functools as ft
from timeit import default_timer as timer

from typing import Optional, List

from homeassistant.const import (
    ATTR_ASSUMED_STATE, ATTR_FRIENDLY_NAME, ATTR_HIDDEN, ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT, DEVICE_DEFAULT_NAME, STATE_OFF, STATE_ON,
    STATE_UNAVAILABLE, STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    ATTR_ENTITY_PICTURE, ATTR_SUPPORTED_FEATURES, ATTR_DEVICE_CLASS)
from homeassistant.core import HomeAssistant
from homeassistant.config import DATA_CUSTOMIZE
from homeassistant.exceptions import NoEntitySpecifiedError
from homeassistant.util import ensure_unique_string, slugify
from homeassistant.util.async import (
    run_coroutine_threadsafe, run_callback_threadsafe)

_LOGGER = logging.getLogger(__name__)
SLOW_UPDATE_WARNING = 10


def generate_entity_id(entity_id_format: str, name: Optional[str],
                       current_ids: Optional[List[str]]=None,
                       hass: Optional[HomeAssistant]=None) -> str:
    """Generate a unique entity ID based on given entity IDs or used IDs."""
    if current_ids is None:
        if hass is None:
            raise ValueError("Missing required parameter currentids or hass")
        else:
            return run_callback_threadsafe(
                hass.loop, async_generate_entity_id, entity_id_format, name,
                current_ids, hass
            ).result()

    name = (name or DEVICE_DEFAULT_NAME).lower()

    return ensure_unique_string(
        entity_id_format.format(slugify(name)), current_ids)


def async_generate_entity_id(entity_id_format: str, name: Optional[str],
                             current_ids: Optional[List[str]]=None,
                             hass: Optional[HomeAssistant]=None) -> str:
    """Generate a unique entity ID based on given entity IDs or used IDs."""
    if current_ids is None:
        if hass is None:
            raise ValueError("Missing required parameter currentids or hass")

        current_ids = hass.states.async_entity_ids()
    name = (name or DEVICE_DEFAULT_NAME).lower()

    return ensure_unique_string(
        entity_id_format.format(slugify(name)), current_ids)


class Entity(object):
    """An abstract class for Home Assistant entities."""

    # pylint: disable=no-self-use
    # SAFE TO OVERWRITE
    # The properties and methods here are safe to overwrite when inheriting
    # this class. These may be used to customize the behavior of the entity.
    entity_id = None  # type: str

    # Owning hass instance. Will be set by EntityComponent
    hass = None  # type: Optional[HomeAssistant]

    # If we reported if this entity was slow
    _slow_reported = False

    # Protect for multiple updates
    _update_staged = False

    # Process updates pararell
    parallel_updates = None

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return "{}.{}".format(self.__class__, id(self))

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return None

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return STATE_UNKNOWN

    @property
    def state_attributes(self):
        """Return the state attributes.

        Implemented by component base class.
        """
        return None

    @property
    def device_state_attributes(self):
        """Return device specific state attributes.

        Implemented by platform classes.
        """
        return None

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return None

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return None

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        return None

    @property
    def hidden(self) -> bool:
        """Return True if the entity should be hidden from UIs."""
        return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return None

    @property
    def force_update(self) -> bool:
        """Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return False

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return None

    def update(self):
        """Retrieve latest state.

        When not implemented, will forward call to async version if available.
        """
        async_update = getattr(self, 'async_update', None)

        if async_update is None:
            return

        # pylint: disable=not-callable
        run_coroutine_threadsafe(async_update(), self.hass.loop).result()

    # DO NOT OVERWRITE
    # These properties and methods are either managed by Home Assistant or they
    # are used to perform a very specific function. Overwriting these may
    # produce undesirable effects in the entity's operation.

    @asyncio.coroutine
    def async_update_ha_state(self, force_refresh=False):
        """Update Home Assistant with current state of entity.

        If force_refresh == True will update entity before setting state.

        This method must be run in the event loop.
        """
        if self.hass is None:
            raise RuntimeError("Attribute hass is None for {}".format(self))

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                "No entity id specified for entity {}".format(self.name))

        # update entity data
        if force_refresh:
            try:
                yield from self.async_device_update()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Update for %s fails", self.entity_id)
                return

        start = timer()

        if not self.available:
            state = STATE_UNAVAILABLE
            attr = {}
        else:
            state = self.state

            if state is None:
                state = STATE_UNKNOWN
            else:
                state = str(state)

            attr = self.state_attributes or {}
            device_attr = self.device_state_attributes
            if device_attr is not None:
                attr.update(device_attr)

        self._attr_setter('unit_of_measurement', str, ATTR_UNIT_OF_MEASUREMENT,
                          attr)

        self._attr_setter('name', str, ATTR_FRIENDLY_NAME, attr)
        self._attr_setter('icon', str, ATTR_ICON, attr)
        self._attr_setter('entity_picture', str, ATTR_ENTITY_PICTURE, attr)
        self._attr_setter('hidden', bool, ATTR_HIDDEN, attr)
        self._attr_setter('assumed_state', bool, ATTR_ASSUMED_STATE, attr)
        self._attr_setter('supported_features', int, ATTR_SUPPORTED_FEATURES,
                          attr)
        self._attr_setter('device_class', str, ATTR_DEVICE_CLASS, attr)

        end = timer()

        if not self._slow_reported and end - start > 0.4:
            self._slow_reported = True
            _LOGGER.warning("Updating state for %s took %.3f seconds. "
                            "Please report platform to the developers at "
                            "https://goo.gl/Nvioub", self.entity_id,
                            end - start)

        # Overwrite properties that have been set in the config file.
        if DATA_CUSTOMIZE in self.hass.data:
            attr.update(self.hass.data[DATA_CUSTOMIZE].get(self.entity_id))

        # Remove hidden property if false so it won't show up.
        if not attr.get(ATTR_HIDDEN, True):
            attr.pop(ATTR_HIDDEN)

        # Convert temperature if we detect one
        try:
            unit_of_measure = attr.get(ATTR_UNIT_OF_MEASUREMENT)
            units = self.hass.config.units
            if (unit_of_measure in (TEMP_CELSIUS, TEMP_FAHRENHEIT) and
                    unit_of_measure != units.temperature_unit):
                prec = len(state) - state.index('.') - 1 if '.' in state else 0
                temp = units.temperature(float(state), unit_of_measure)
                state = str(round(temp) if prec == 0 else round(temp, prec))
                attr[ATTR_UNIT_OF_MEASUREMENT] = units.temperature_unit
        except ValueError:
            # Could not convert state to float
            pass

        self.hass.states.async_set(
            self.entity_id, state, attr, self.force_update)

    def schedule_update_ha_state(self, force_refresh=False):
        """Schedule a update ha state change task.

        That avoid executor dead looks.
        """
        self.hass.add_job(self.async_update_ha_state(force_refresh))

    def async_schedule_update_ha_state(self, force_refresh=False):
        """Schedule a update ha state change task."""
        self.hass.async_add_job(self.async_update_ha_state(force_refresh))

    def async_device_update(self, warning=True):
        """Process 'update' or 'async_update' from entity.

        This method is a coroutine.
        """
        if self._update_staged:
            return
        self._update_staged = True

        # Process update sequential
        if self.parallel_updates:
            yield from self.parallel_updates.acquire()

        if warning:
            update_warn = self.hass.loop.call_later(
                SLOW_UPDATE_WARNING, _LOGGER.warning,
                "Update of %s is taking over %s seconds", self.entity_id,
                SLOW_UPDATE_WARNING
            )

        try:
            if hasattr(self, 'async_update'):
                # pylint: disable=no-member
                yield from self.async_update()
            else:
                yield from self.hass.async_add_job(self.update)
        finally:
            self._update_staged = False
            if warning:
                update_warn.cancel()
            if self.parallel_updates:
                self.parallel_updates.release()

    def remove(self) -> None:
        """Remove entity from HASS."""
        run_coroutine_threadsafe(
            self.async_remove(), self.hass.loop
        ).result()

    @asyncio.coroutine
    def async_remove(self) -> None:
        """Remove entity from async HASS.

        This method must be run in the event loop.
        """
        self.hass.states.async_remove(self.entity_id)

    def _attr_setter(self, name, typ, attr, attrs):
        """Populate attributes based on properties."""
        if attr in attrs:
            return

        value = getattr(self, name)

        if value is None:
            return

        try:
            attrs[attr] = typ(value)
        except (TypeError, ValueError):
            pass

    def __eq__(self, other):
        """Return the comparison."""
        return (isinstance(other, Entity) and
                other.unique_id == self.unique_id)

    def __repr__(self):
        """Return the representation."""
        return "<Entity {}: {}>".format(self.name, self.state)


class ToggleEntity(Entity):
    """An abstract class for entities that can be turned on and off."""

    # pylint: disable=no-self-use
    @property
    def state(self) -> str:
        """Return the state."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        raise NotImplementedError()

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        raise NotImplementedError()

    def async_turn_on(self, **kwargs):
        """Turn the entity on.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        raise NotImplementedError()

    def async_turn_off(self, **kwargs):
        """Turn the entity off.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.turn_off, **kwargs))

    def toggle(self, **kwargs) -> None:
        """Toggle the entity."""
        if self.is_on:
            self.turn_off(**kwargs)
        else:
            self.turn_on(**kwargs)

    def async_toggle(self, **kwargs):
        """Toggle the entity.

        This method must be run in the event loop and returns a coroutine.
        """
        if self.is_on:
            return self.async_turn_off(**kwargs)
        return self.async_turn_on(**kwargs)
