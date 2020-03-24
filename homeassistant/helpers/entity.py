"""An abstract class for entities."""
from abc import ABC
import asyncio
from datetime import datetime, timedelta
import functools as ft
import logging
from timeit import default_timer as timer
from typing import Any, Dict, Iterable, List, Optional, Union

from homeassistant.config import DATA_CUSTOMIZE
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_HIDDEN,
    ATTR_ICON,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_DEFAULT_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import NoEntitySpecifiedError
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.entity_registry import (
    EVENT_ENTITY_REGISTRY_UPDATED,
    RegistryEntry,
)
from homeassistant.util import dt as dt_util, ensure_unique_string, slugify
from homeassistant.util.async_ import run_callback_threadsafe

# mypy: allow-untyped-defs, no-check-untyped-defs, no-warn-return-any

_LOGGER = logging.getLogger(__name__)
SLOW_UPDATE_WARNING = 10


def generate_entity_id(
    entity_id_format: str,
    name: Optional[str],
    current_ids: Optional[List[str]] = None,
    hass: Optional[HomeAssistant] = None,
) -> str:
    """Generate a unique entity ID based on given entity IDs or used IDs."""
    if current_ids is None:
        if hass is None:
            raise ValueError("Missing required parameter currentids or hass")
        return run_callback_threadsafe(
            hass.loop,
            async_generate_entity_id,
            entity_id_format,
            name,
            current_ids,
            hass,
        ).result()

    name = (slugify(name or "") or slugify(DEVICE_DEFAULT_NAME)).lower()

    return ensure_unique_string(entity_id_format.format(name), current_ids)


@callback
def async_generate_entity_id(
    entity_id_format: str,
    name: Optional[str],
    current_ids: Optional[Iterable[str]] = None,
    hass: Optional[HomeAssistant] = None,
) -> str:
    """Generate a unique entity ID based on given entity IDs or used IDs."""
    if current_ids is None:
        if hass is None:
            raise ValueError("Missing required parameter currentids or hass")

        current_ids = hass.states.async_entity_ids()
    name = (name or DEVICE_DEFAULT_NAME).lower()

    return ensure_unique_string(entity_id_format.format(slugify(name)), current_ids)


class Entity(ABC):
    """An abstract class for Home Assistant entities."""

    # SAFE TO OVERWRITE
    # The properties and methods here are safe to overwrite when inheriting
    # this class. These may be used to customize the behavior of the entity.
    entity_id = None  # type: str

    # Owning hass instance. Will be set by EntityPlatform
    hass: Optional[HomeAssistant] = None

    # Owning platform instance. Will be set by EntityPlatform
    platform: Optional[EntityPlatform] = None

    # If we reported if this entity was slow
    _slow_reported = False

    # If we reported this entity is updated while disabled
    _disabled_reported = False

    # Protect for multiple updates
    _update_staged = False

    # Process updates in parallel
    parallel_updates: Optional[asyncio.Semaphore] = None

    # Entry in the entity registry
    registry_entry: Optional[RegistryEntry] = None

    # Hold list for functions to call on remove.
    _on_remove: Optional[List[CALLBACK_TYPE]] = None

    # Context
    _context: Optional[Context] = None
    _context_set: Optional[datetime] = None

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return None

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return None

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the entity."""
        return STATE_UNKNOWN

    @property
    def capability_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the capability attributes.

        Attributes that explain the capabilities of an entity.

        Implemented by component base class. Convention for attribute names
        is lowercase snake_case.
        """
        return None

    @property
    def state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes.

        Implemented by component base class. Convention for attribute names
        is lowercase snake_case.
        """
        return None

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return device specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        return None

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return None

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return None

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of this entity, if any."""
        return None

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return None

    @property
    def entity_picture(self) -> Optional[str]:
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
        return False

    @property
    def force_update(self) -> bool:
        """Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return False

    @property
    def supported_features(self) -> Optional[int]:
        """Flag supported features."""
        return None

    @property
    def context_recent_time(self) -> timedelta:
        """Time that a context is considered recent."""
        return timedelta(seconds=5)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    # DO NOT OVERWRITE
    # These properties and methods are either managed by Home Assistant or they
    # are used to perform a very specific function. Overwriting these may
    # produce undesirable effects in the entity's operation.

    @property
    def enabled(self) -> bool:
        """Return if the entity is enabled in the entity registry.

        If an entity is not part of the registry, it cannot be disabled
        and will therefore always be enabled.
        """
        return self.registry_entry is None or not self.registry_entry.disabled

    @callback
    def async_set_context(self, context: Context) -> None:
        """Set the context the entity currently operates under."""
        self._context = context
        self._context_set = dt_util.utcnow()

    async def async_update_ha_state(self, force_refresh=False):
        """Update Home Assistant with current state of entity.

        If force_refresh == True will update entity before setting state.

        This method must be run in the event loop.
        """
        if self.hass is None:
            raise RuntimeError(f"Attribute hass is None for {self}")

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                f"No entity id specified for entity {self.name}"
            )

        # update entity data
        if force_refresh:
            try:
                await self.async_device_update()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Update for %s fails", self.entity_id)
                return

        self._async_write_ha_state()

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the state machine."""
        if self.hass is None:
            raise RuntimeError(f"Attribute hass is None for {self}")

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                f"No entity id specified for entity {self.name}"
            )

        self._async_write_ha_state()  # type: ignore

    @callback
    def _async_write_ha_state(self):
        """Write the state to the state machine."""
        if self.registry_entry and self.registry_entry.disabled_by:
            if not self._disabled_reported:
                self._disabled_reported = True
                _LOGGER.warning(
                    "Entity %s is incorrectly being triggered for updates while it is disabled. This is a bug in the %s integration.",
                    self.entity_id,
                    self.platform.platform_name,
                )
            return

        start = timer()

        attr = self.capability_attributes
        attr = dict(attr) if attr else {}

        if not self.available:
            state = STATE_UNAVAILABLE
        else:
            state = self.state

            if state is None:
                state = STATE_UNKNOWN
            else:
                state = str(state)

            attr.update(self.state_attributes or {})
            attr.update(self.device_state_attributes or {})

        unit_of_measurement = self.unit_of_measurement
        if unit_of_measurement is not None:
            attr[ATTR_UNIT_OF_MEASUREMENT] = unit_of_measurement

        entry = self.registry_entry
        # pylint: disable=consider-using-ternary
        name = (entry and entry.name) or self.name
        if name is not None:
            attr[ATTR_FRIENDLY_NAME] = name

        icon = (entry and entry.icon) or self.icon
        if icon is not None:
            attr[ATTR_ICON] = icon

        entity_picture = self.entity_picture
        if entity_picture is not None:
            attr[ATTR_ENTITY_PICTURE] = entity_picture

        hidden = self.hidden
        if hidden:
            attr[ATTR_HIDDEN] = hidden

        assumed_state = self.assumed_state
        if assumed_state:
            attr[ATTR_ASSUMED_STATE] = assumed_state

        supported_features = self.supported_features
        if supported_features is not None:
            attr[ATTR_SUPPORTED_FEATURES] = supported_features

        device_class = self.device_class
        if device_class is not None:
            attr[ATTR_DEVICE_CLASS] = str(device_class)

        end = timer()

        if end - start > 0.4 and not self._slow_reported:
            self._slow_reported = True
            extra = ""
            if "custom_components" in type(self).__module__:
                extra = "Please report it to the custom component author."
            else:
                extra = (
                    "Please create a bug report at "
                    "https://github.com/home-assistant/home-assistant/issues?q=is%3Aopen+is%3Aissue"
                )
                if self.platform:
                    extra += (
                        f"+label%3A%22integration%3A+{self.platform.platform_name}%22"
                    )

            _LOGGER.warning(
                "Updating state for %s (%s) took %.3f seconds. %s",
                self.entity_id,
                type(self),
                end - start,
                extra,
            )

        # Overwrite properties that have been set in the config file.
        if DATA_CUSTOMIZE in self.hass.data:
            attr.update(self.hass.data[DATA_CUSTOMIZE].get(self.entity_id))

        # Convert temperature if we detect one
        try:
            unit_of_measure = attr.get(ATTR_UNIT_OF_MEASUREMENT)
            units = self.hass.config.units
            if (
                unit_of_measure in (TEMP_CELSIUS, TEMP_FAHRENHEIT)
                and unit_of_measure != units.temperature_unit
            ):
                prec = len(state) - state.index(".") - 1 if "." in state else 0
                temp = units.temperature(float(state), unit_of_measure)
                state = str(round(temp) if prec == 0 else round(temp, prec))
                attr[ATTR_UNIT_OF_MEASUREMENT] = units.temperature_unit
        except ValueError:
            # Could not convert state to float
            pass

        if (
            self._context is not None
            and dt_util.utcnow() - self._context_set > self.context_recent_time
        ):
            self._context = None
            self._context_set = None

        self.hass.states.async_set(
            self.entity_id, state, attr, self.force_update, self._context
        )

    def schedule_update_ha_state(self, force_refresh=False):
        """Schedule an update ha state change task.

        Scheduling the update avoids executor deadlocks.

        Entity state and attributes are read when the update ha state change
        task is executed.
        If state is changed more than once before the ha state change task has
        been executed, the intermediate state transitions will be missed.
        """
        self.hass.add_job(self.async_update_ha_state(force_refresh))

    @callback
    def async_schedule_update_ha_state(self, force_refresh=False):
        """Schedule an update ha state change task.

        This method must be run in the event loop.
        Scheduling the update avoids executor deadlocks.

        Entity state and attributes are read when the update ha state change
        task is executed.
        If state is changed more than once before the ha state change task has
        been executed, the intermediate state transitions will be missed.
        """
        if force_refresh:
            self.hass.async_create_task(self.async_update_ha_state(force_refresh))
        else:
            self.async_write_ha_state()

    async def async_device_update(self, warning=True):
        """Process 'update' or 'async_update' from entity.

        This method is a coroutine.
        """
        if self._update_staged:
            return
        self._update_staged = True

        # Process update sequential
        if self.parallel_updates:
            await self.parallel_updates.acquire()

        if warning:
            update_warn = self.hass.loop.call_later(
                SLOW_UPDATE_WARNING,
                _LOGGER.warning,
                "Update of %s is taking over %s seconds",
                self.entity_id,
                SLOW_UPDATE_WARNING,
            )

        try:
            # pylint: disable=no-member
            if hasattr(self, "async_update"):
                await self.async_update()
            elif hasattr(self, "update"):
                await self.hass.async_add_executor_job(self.update)
        finally:
            self._update_staged = False
            if warning:
                update_warn.cancel()
            if self.parallel_updates:
                self.parallel_updates.release()

    @callback
    def async_on_remove(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when entity removed."""
        if self._on_remove is None:
            self._on_remove = []
        self._on_remove.append(func)

    async def async_removed_from_registry(self) -> None:
        """Run when entity has been removed from entity registry.

        To be extended by integrations.
        """

    async def async_remove(self) -> None:
        """Remove entity from Home Assistant."""
        assert self.hass is not None
        await self.async_internal_will_remove_from_hass()
        await self.async_will_remove_from_hass()

        if self._on_remove is not None:
            while self._on_remove:
                self._on_remove.pop()()

        self.hass.states.async_remove(self.entity_id, context=self._context)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.

        To be extended by integrations.
        """

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        To be extended by integrations.
        """

    async def async_internal_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.

        Not to be extended by integrations.
        """
        if self.registry_entry is not None:
            assert self.hass is not None
            self.async_on_remove(
                self.hass.bus.async_listen(
                    EVENT_ENTITY_REGISTRY_UPDATED, self._async_registry_updated
                )
            )

    async def async_internal_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        Not to be extended by integrations.
        """

    async def _async_registry_updated(self, event):
        """Handle entity registry update."""
        data = event.data
        if data["action"] == "remove" and data["entity_id"] == self.entity_id:
            await self.async_removed_from_registry()

        if (
            data["action"] != "update"
            or data.get("old_entity_id", data["entity_id"]) != self.entity_id
        ):
            return

        ent_reg = await self.hass.helpers.entity_registry.async_get_registry()
        old = self.registry_entry
        self.registry_entry = ent_reg.async_get(data["entity_id"])

        if self.registry_entry.disabled_by is not None:
            await self.async_remove()
            return

        if self.registry_entry.entity_id == old.entity_id:
            self.async_write_ha_state()
            return

        await self.async_remove()

        self.entity_id = self.registry_entry.entity_id
        await self.platform.async_add_entities([self])

    def __eq__(self, other):
        """Return the comparison."""
        if not isinstance(other, self.__class__):
            return False

        # Can only decide equality if both have a unique id
        if self.unique_id is None or other.unique_id is None:
            return False

        # Ensure they belong to the same platform
        if self.platform is not None or other.platform is not None:
            if self.platform is None or other.platform is None:
                return False

            if self.platform.platform != other.platform.platform:
                return False

        return self.unique_id == other.unique_id

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<Entity {self.name}: {self.state}>"

    # call an requests
    async def async_request_call(self, coro):
        """Process request batched."""
        if self.parallel_updates:
            await self.parallel_updates.acquire()

        try:
            await coro
        finally:
            if self.parallel_updates:
                self.parallel_updates.release()


class ToggleEntity(Entity):
    """An abstract class for entities that can be turned on and off."""

    @property
    def state(self) -> str:
        """Return the state."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        raise NotImplementedError()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        raise NotImplementedError()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_job(ft.partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        raise NotImplementedError()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_job(ft.partial(self.turn_off, **kwargs))

    def toggle(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if self.is_on:
            self.turn_off(**kwargs)
        else:
            self.turn_on(**kwargs)

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        if self.is_on:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)
