"""Vistapool Light entities."""

from typing import Any, override

from aioaquarite import AquariteError

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import DOMAIN, SIGNAL_NEW_POOL
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 1

_VALUE_PATH = "light.status"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vistapool light for every pool on the account."""
    async_add_entities(
        VistapoolLight(coordinator)
        for coordinator in entry.runtime_data.coordinators.values()
    )

    @callback
    def _async_add_pool(coordinator: VistapoolDataUpdateCoordinator) -> None:
        async_add_entities([VistapoolLight(coordinator)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_NEW_POOL}_{entry.entry_id}", _async_add_pool
        )
    )


class VistapoolLight(VistapoolEntity, LightEntity):
    """Representation of a Vistapool pool light."""

    _attr_translation_key = "pool_light"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: VistapoolDataUpdateCoordinator) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator)
        self._attr_unique_id = self.build_unique_id("pool_light")  # pylint: disable=home-assistant-entity-unique-id-redundant-platform

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        value = self.coordinator.get_value(_VALUE_PATH)
        if value is None:
            return None
        return value in (True, "1")

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._async_set_value(1)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_set_value(0)

    async def _async_set_value(self, value: int) -> None:
        """Send a value update via the Vistapool cloud API."""
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id, _VALUE_PATH, value
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
        self.coordinator.apply_optimistic(_VALUE_PATH, value)
