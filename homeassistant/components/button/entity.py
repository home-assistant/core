"""Base entity for the Button platform."""

from typing import final, override

from propcache.api import cached_property

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import ButtonDeviceClass


class ButtonEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes button entities."""

    device_class: ButtonDeviceClass | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
}


class ButtonEntity(RestoreEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a Button entity."""

    entity_description: ButtonEntityDescription
    _attr_should_poll = False
    _attr_device_class: ButtonDeviceClass | None
    _attr_state: None = None
    __last_pressed_isoformat: str | None = None

    @override
    def _default_to_device_class_name(self) -> bool:
        """Return True if an unnamed entity should be named by its device class.

        For buttons this is True if the entity has a device class.
        """
        return self.device_class is not None

    @cached_property
    @override
    def device_class(self) -> ButtonDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @cached_property
    @final
    @override
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_pressed_isoformat

    def __set_state(self, state: str | None) -> None:
        """Set the entity state."""
        # Invalidate the cache of the cached property
        self.__dict__.pop("state", None)
        self.__last_pressed_isoformat = state

    @final
    async def _async_press_action(self) -> None:
        """Press the button (from e.g., service call).

        Should not be overridden, handle setting last press timestamp.
        """
        self.__set_state(dt_util.utcnow().isoformat())
        self.async_write_ha_state()
        await self.async_press()

    @override
    async def async_internal_added_to_hass(self) -> None:
        """Call when the button is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, None):
            self.__set_state(state.state)

    def press(self) -> None:
        """Press the button."""
        raise NotImplementedError

    async def async_press(self) -> None:
        """Press the button."""
        await self.hass.async_add_executor_job(self.press)
