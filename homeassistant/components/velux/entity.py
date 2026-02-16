"""Support for VELUX KLF 200 devices."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, ParamSpec

from pyvlx import Node, PyVLXException

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

P = ParamSpec("P")


def wrap_pyvlx_call_exceptions(
    func: Callable[P, Coroutine[Any, Any, None]],
) -> Callable[P, Coroutine[Any, Any, None]]:
    """Decorate pyvlx calls to handle exceptions.

    Catches OSError and PyVLXException and wraps them into HomeAssistantError
    with translation support.
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        """Wrap async function to catch exceptions thrown in pyvlx calls."""
        try:
            await func(*args, **kwargs)
        except (OSError, PyVLXException) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

    return wrapper


class VeluxEntity(Entity):
    """Abstraction for all Velux entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    update_callback: Callable[[Node], Awaitable[None]] | None = None
    _attr_available = True
    _unavailable_logged = False

    def __init__(self, node: Node, config_entry_id: str) -> None:
        """Initialize the Velux device."""
        self.node = node
        unique_id = node.serial_number or f"{config_entry_id}_{node.node_id}"
        self._attr_unique_id = unique_id
        self.unsubscribe = None

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    unique_id,
                )
            },
            name=node.name or f"#{node.node_id}",
            serial_number=node.serial_number,
            via_device=(DOMAIN, f"gateway_{config_entry_id}"),
        )

    async def after_update_callback(self, node) -> None:
        """Call after device was updated."""
        self._attr_available = self.node.pyvlx.get_connected()
        if not self._attr_available:
            if not self._unavailable_logged:
                _LOGGER.info("Entity %s is unavailable", self.entity_id)
                self._unavailable_logged = True
        elif self._unavailable_logged:
            _LOGGER.info("Entity %s is back online", self.entity_id)
            self._unavailable_logged = False

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback and store reference for cleanup."""

        self.update_callback = self.after_update_callback
        self.node.register_device_updated_cb(self.update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up registered callbacks."""
        if self.update_callback:
            self.node.unregister_device_updated_cb(self.update_callback)
            self.update_callback = None
