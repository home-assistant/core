"""Creates a switch entity for the mower."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from aioautomower.exceptions import ApiException
from aioautomower.model import (
    MowerActivities,
    MowerStates,
    RestrictedReasons,
    StayOutZones,
    Zone,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerControlEntity

_LOGGER = logging.getLogger(__name__)

ERROR_ACTIVITIES = (
    MowerActivities.STOPPED_IN_GARDEN,
    MowerActivities.UNKNOWN,
    MowerActivities.NOT_APPLICABLE,
)
ERROR_STATES = [
    MowerStates.FATAL_ERROR,
    MowerStates.ERROR,
    MowerStates.ERROR_AT_POWER_UP,
    MowerStates.NOT_APPLICABLE,
    MowerStates.UNKNOWN,
    MowerStates.STOPPED,
    MowerStates.OFF,
]
EXECUTION_TIME = 5


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch platform."""
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = []
    entities.extend(
        AutomowerScheduleSwitchEntity(mower_id, coordinator)
        for mower_id in coordinator.data
    )
    for mower_id in coordinator.data:
        if coordinator.data[mower_id].capabilities.stay_out_zones:
            _stay_out_zones = coordinator.data[mower_id].stay_out_zones
            if _stay_out_zones is not None:
                entities.extend(
                    AutomowerStayOutZoneSwitchEntity(
                        coordinator, mower_id, stay_out_zone_uid
                    )
                    for stay_out_zone_uid in _stay_out_zones.zones
                )
            async_remove_entities(hass, coordinator, entry, mower_id)
    async_add_entities(entities)


class AutomowerScheduleSwitchEntity(AutomowerControlEntity, SwitchEntity):
    """Defining the Automower schedule switch."""

    _attr_translation_key = "enable_schedule"

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Set up Automower switch."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = f"{self.mower_id}_{self._attr_translation_key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        attributes = self.mower_attributes
        return not (
            attributes.mower.state == MowerStates.RESTRICTED
            and attributes.planner.restricted_reason == RestrictedReasons.NOT_APPLICABLE
        )

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available and (
            self.mower_attributes.mower.state not in ERROR_STATES
            or self.mower_attributes.mower.activity not in ERROR_ACTIVITIES
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            await self.coordinator.api.commands.park_until_further_notice(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.coordinator.api.commands.resume_schedule(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception


class AutomowerStayOutZoneSwitchEntity(AutomowerControlEntity, SwitchEntity):
    """Defining the Automower stay out zone switch."""

    _attr_translation_key = "stay_out_zones"

    def __init__(
        self,
        coordinator: AutomowerDataUpdateCoordinator,
        mower_id: str,
        stay_out_zone_uid: str,
    ) -> None:
        """Set up Automower switch."""
        super().__init__(mower_id, coordinator)
        self.coordinator = coordinator
        self.stay_out_zone_uid = stay_out_zone_uid
        self._attr_unique_id = (
            f"{self.mower_id}_{stay_out_zone_uid}_{self._attr_translation_key}"
        )
        self._attr_translation_placeholders = {"stay_out_zone": self.stay_out_zone.name}

    @property
    def stay_out_zones(self) -> StayOutZones:
        """Return all stay out zones."""
        if TYPE_CHECKING:
            assert self.mower_attributes.stay_out_zones is not None
        return self.mower_attributes.stay_out_zones

    @property
    def stay_out_zone(self) -> Zone:
        """Return the specific stay out zone."""
        return self.stay_out_zones.zones[self.stay_out_zone_uid]

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.stay_out_zone.enabled

    @property
    def available(self) -> bool:
        """Return True if the device is available and the zones are not `dirty`."""
        return super().available and not self.stay_out_zones.dirty

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.api.commands.switch_stay_out_zone(
                self.mower_id, self.stay_out_zone_uid, False
            )
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception
        else:
            # As there are no updates from the websocket regarding stay out zone changes,
            # we need to wait until the command is executed and then poll the API.
            await asyncio.sleep(EXECUTION_TIME)
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.api.commands.switch_stay_out_zone(
                self.mower_id, self.stay_out_zone_uid, True
            )
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception
        else:
            # As there are no updates from the websocket regarding stay out zone changes,
            # we need to wait until the command is executed and then poll the API.
            await asyncio.sleep(EXECUTION_TIME)
            await self.coordinator.async_request_refresh()


@callback
def async_remove_entities(
    hass: HomeAssistant,
    coordinator: AutomowerDataUpdateCoordinator,
    config_entry: ConfigEntry,
    mower_id: str,
) -> None:
    """Remove deleted stay-out-zones from Home Assistant."""
    entity_reg = er.async_get(hass)
    active_zones = set()
    _zones = coordinator.data[mower_id].stay_out_zones
    if _zones is not None:
        for zones_uid in _zones.zones:
            uid = f"{mower_id}_{zones_uid}_stay_out_zones"
            active_zones.add(uid)
    for entity_entry in er.async_entries_for_config_entry(
        entity_reg, config_entry.entry_id
    ):
        if (
            (split := entity_entry.unique_id.split("_"))[0] == mower_id
            and split[-1] == "zones"
            and entity_entry.unique_id not in active_zones
        ):
            entity_reg.async_remove(entity_entry.entity_id)
