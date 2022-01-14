"""The lookin integration light platform."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any, cast

from aiolookin import Remote
from aiolookin.models import UDPCommandType, UDPEvent

from homeassistant.components.light import COLOR_MODE_ONOFF, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import LookinPowerEntity
from .models import LookinData

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light platform for lookin from a config entry."""
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for remote in lookin_data.devices:
        if remote["Type"] != "03":
            continue
        uuid = remote["UUID"]

        def _wrap_async_update(
            uuid: str,
        ) -> Callable[[], Coroutine[None, Any, Remote]]:
            """Create a function to capture the uuid cell variable."""

            async def _async_update() -> Remote:
                return await lookin_data.lookin_protocol.get_remote(uuid)

            return _async_update

        coordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{config_entry.title} {uuid}",
            update_method=_wrap_async_update(uuid),
            update_interval=timedelta(
                seconds=60
            ),  # Updates are pushed (fallback is polling)
        )
        await coordinator.async_refresh()
        device: Remote = coordinator.data

        entities.append(
            LookinLightEntity(
                uuid=uuid,
                device=device,
                lookin_data=lookin_data,
                coordinator=coordinator,
            )
        )

    async_add_entities(entities)


class LookinLightEntity(LookinPowerEntity, LightEntity):
    """A lookin IR controlled light."""

    _attr_supported_color_modes = {COLOR_MODE_ONOFF}
    _attr_color_mode = COLOR_MODE_ONOFF

    def __init__(
        self,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Init the light."""
        super().__init__(coordinator, uuid, device, lookin_data)
        self._attr_is_on = False

    @property
    def _remote(self) -> Remote:
        return cast(Remote, self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._async_send_command(self._power_on_command)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_send_command(self._power_off_command)
        self._attr_is_on = False
        self.async_write_ha_state()

    def _update_from_status(self, status: str) -> None:
        """Update media property from status.

        1000
        0 - 0/1 on/off
        """
        if len(status) != 4:
            return
        state = status[0]

        self._attr_is_on = state == "1"

    def _async_push_update(self, event: UDPEvent) -> None:
        """Process an update pushed via UDP."""
        LOGGER.debug("Processing push message for %s: %s", self.entity_id, event)
        self._update_from_status(event.value)
        self.coordinator.async_set_updated_data(self._remote)
        self.async_write_ha_state()

    async def _async_push_update_device(self, event: UDPEvent) -> None:
        """Process an update pushed via UDP."""
        LOGGER.debug("Processing push message for %s: %s", self.entity_id, event)
        await self.coordinator.async_refresh()
        self._attr_name = self._remote.name

    async def async_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_event(
                self._lookin_device.id,
                UDPCommandType.ir,
                self._uuid,
                self._async_push_update,
            )
        )
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_event(
                self._lookin_device.id,
                UDPCommandType.data,
                self._uuid,
                self._async_push_update_device,
            )
        )
