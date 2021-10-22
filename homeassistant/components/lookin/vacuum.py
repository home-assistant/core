"""The lookin integration vacuum platform."""
from __future__ import annotations

from typing import Any

from aiolookin import Remote

from homeassistant.components.vacuum import (
    SERVICE_START,
    SERVICE_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    VacuumEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LookinPowerEntity
from .models import LookinData

SUPPORT_FLAGS: int = SUPPORT_TURN_ON | SUPPORT_TURN_OFF


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the lookin vacuums."""
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for remote in lookin_data.devices:
        if remote["Type"] != "06":
            continue
        uuid = remote["UUID"]
        device = await lookin_data.lookin_protocol.get_remote(uuid)
        entities.append(
            LookinVacuum(
                uuid=uuid,
                device=device,
                lookin_data=lookin_data,
            )
        )

    async_add_entities(entities)


class LookinVacuum(LookinPowerEntity, VacuumEntity):
    """Representation of a lookin vacuum."""

    def __init__(
        self,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
    ) -> None:
        """Initialize the vacuum."""
        super().__init__(uuid, device, lookin_data)
        self._status = SERVICE_STOP

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def supported_features(self) -> int | None:
        """Flag supported features."""
        return SUPPORT_FLAGS

    @property
    def is_on(self) -> bool:
        """Return true if vacuum is on."""
        return self._status != SERVICE_STOP

    @property
    def status(self) -> str:
        """Return the status of the vacuum."""
        return self._status

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the vacuum."""
        await self._async_send_command(self._power_on_command)
        self._status = SERVICE_START
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the vacuum."""
        await self._async_send_command(self._power_off_command)
        self._status = SERVICE_STOP
        self.async_write_ha_state()
