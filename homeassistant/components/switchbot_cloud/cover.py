"""Support for the Switchbot BlindTilt, Curtain, Curtain3, RollerShade as Cover."""

import asyncio
from typing import Any

from switchbot_api import (
    BlindTiltCommands,
    CommonCommands,
    CurtainCommands,
    Device,
    Remote,
    RollerShadeCommands,
    SwitchBotAPI,
)

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import COVER_ENTITY_AFTER_COMMAND_REFRESH, DOMAIN
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.covers
    )


class SwitchBotCloudCover(SwitchBotCloudEntity, CoverEntity):
    """Representation of a SwitchBot Cover."""

    _attr_name = None
    _attr_is_closed: bool | None = None

    def _set_attributes(self) -> None:
        if self.coordinator.data is None:
            return
        position: int | None = self.coordinator.data.get("slidePosition")
        if position is None:
            return
        self._attr_current_cover_position = 100 - position
        self._attr_current_cover_tilt_position = 100 - position
        self._attr_is_closed = position == 100


class SwitchBotCloudCoverCurtain(SwitchBotCloudCover):
    """Representation of a SwitchBot Curtain & Curtain3."""

    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(CommonCommands.ON)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position: int | None = kwargs.get("position")
        if position is not None:
            await self.send_api_command(
                CurtainCommands.SET_POSITION,
                parameters=f"{0},ff,{100 - position}",
            )
            await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
            await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.send_api_command(CurtainCommands.PAUSE)
        await self.coordinator.async_request_refresh()


class SwitchBotCloudCoverRollerShade(SwitchBotCloudCover):
    """Representation of a SwitchBot RollerShade."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
    )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(RollerShadeCommands.SET_POSITION, parameters=str(0))
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.send_api_command(
            RollerShadeCommands.SET_POSITION, parameters=str(100)
        )
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position: int | None = kwargs.get("position")
        if position is not None:
            await self.send_api_command(
                RollerShadeCommands.SET_POSITION, parameters=str(100 - position)
            )
            await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
            await self.coordinator.async_request_refresh()


class SwitchBotCloudCoverBlindTilt(SwitchBotCloudCover):
    """Representation of a SwitchBot Blind Tilt."""

    _attr_direction: str | None = None
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.SET_TILT_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
    )

    def _set_attributes(self) -> None:
        if self.coordinator.data is None:
            return
        position: int | None = self.coordinator.data.get("slidePosition")
        if position is None:
            return
        self._attr_is_closed = position in [0, 100]
        if position > 50:
            percent = 100 - ((position - 50) * 2)
        else:
            percent = 100 - (50 - position) * 2
        self._attr_current_cover_position = percent
        self._attr_current_cover_tilt_position = percent
        direction = self.coordinator.data.get("direction")
        self._attr_direction = direction.lower() if direction else None

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        percent: int | None = kwargs.get("tilt_position")
        if percent is not None:
            await self.send_api_command(
                BlindTiltCommands.SET_POSITION,
                parameters=f"{self._attr_direction};{percent}",
            )
            await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
            await self.coordinator.async_request_refresh()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(BlindTiltCommands.FULLY_OPEN)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._attr_direction is not None:
            if "up" in self._attr_direction:
                await self.send_api_command(BlindTiltCommands.CLOSE_UP)
            else:
                await self.send_api_command(BlindTiltCommands.CLOSE_DOWN)
            await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
            await self.coordinator.async_request_refresh()


class SwitchBotCloudCoverGarageDoorOpener(SwitchBotCloudCover):
    """Representation of a SwitchBot Garage Door Opener."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )

    def _set_attributes(self) -> None:
        if self.coordinator.data is None:
            return
        door_status: int | None = self.coordinator.data.get("doorStatus")
        self._attr_is_closed = None if door_status is None else door_status == 1

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(CommonCommands.ON)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> (
    SwitchBotCloudCoverBlindTilt
    | SwitchBotCloudCoverRollerShade
    | SwitchBotCloudCoverCurtain
    | SwitchBotCloudCoverGarageDoorOpener
):
    """Make a SwitchBotCloudCover device."""
    if device.device_type == "Blind Tilt":
        return SwitchBotCloudCoverBlindTilt(api, device, coordinator)
    if device.device_type == "Roller Shade":
        return SwitchBotCloudCoverRollerShade(api, device, coordinator)
    if device.device_type == "Garage Door Opener":
        return SwitchBotCloudCoverGarageDoorOpener(api, device, coordinator)
    return SwitchBotCloudCoverCurtain(api, device, coordinator)
