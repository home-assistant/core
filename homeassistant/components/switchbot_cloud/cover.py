"""Support for the Switchbot Bot as a Cover."""

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import DOMAIN
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
    _attr_direction: str | None = None

    def _set_attributes(self) -> None:
        if self.coordinator.data is None:
            return
        position: int | None = self.coordinator.data.get("slidePosition")
        if position is None:
            return
        position = 100 - position

        self._attr_is_closed = position == 0

        self._attr_direction = self.coordinator.data.get("direction")
        if self._attr_direction is not None:
            self._attr_direction = self._attr_direction.lower()

        self._attr_current_cover_position = position
        self._attr_current_cover_tilt_position = position
        self.async_write_ha_state()


class SwitchBotCloudCoverCurtain(SwitchBotCloudCover):
    """Representation of a SwitchBot Cover."""

    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_device_class = CoverDeviceClass.CURTAIN

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(CommonCommands.ON)
        self._attr_is_closed = False
        self._attr_current_cover_position = 100
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.send_api_command(CommonCommands.OFF)
        self._attr_current_cover_position = 0
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position: int | None = kwargs.get("position")
        if position is not None:
            await self.send_api_command(
                CurtainCommands.SET_POSITION,
                parameters=f"{0},ff,{100 - position}",
            )
            self._attr_current_cover_position = position
            self._attr_is_closed = position == 0
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.send_api_command(CurtainCommands.PAUSE)
        await asyncio.sleep(2)
        response: dict | None = await self._api.get_status(self.unique_id)
        position: int | None = response.get("slidePosition") if response else None
        if position is None:
            return
        self._attr_is_closed = position == 0
        self._attr_current_cover_position = position
        self.async_write_ha_state()


class SwitchBotCloudCoverTilt(SwitchBotCloudCover):
    """Representation of a SwitchBot Cover."""

    _attr_name = None
    _attr_is_closed: bool | None = None
    _attr_percent: int | None = None

    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.SET_TILT_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
    )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        percent: int | None = kwargs.get("tilt_position")
        if percent is not None:
            await self.send_api_command(
                BlindTiltCommands.SET_POSITION,
                parameters=f"{self._attr_direction};{percent}",
            )
            await asyncio.sleep(1)
            await self.__update_current_cover_tilt_position()
            self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(BlindTiltCommands.FULLY_OPEN)
        self._attr_is_closed = False
        await asyncio.sleep(1)
        await self.__update_current_cover_tilt_position()
        self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._attr_direction is not None:
            if "up" in self._attr_direction:
                await self.send_api_command(BlindTiltCommands.CLOSE_UP)
            else:
                await self.send_api_command(BlindTiltCommands.CLOSE_DOWN)
            self._attr_is_closed = True
            await asyncio.sleep(1)
            await self.__update_current_cover_tilt_position()
            self.async_write_ha_state()

    def _set_attributes(self) -> None:
        if self.coordinator.data is None:
            return
        position: int | None = self.coordinator.data.get("slidePosition")
        if position is not None:
            self._attr_is_closed = position in [0, 100]
            if position > 50:
                percent = 100 - ((position - 50) * 2)
            else:
                percent = 100 - (50 - position) * 2
            self._attr_direction = self.coordinator.data.get("direction")
            if self._attr_direction is not None:
                self._attr_direction = self._attr_direction.lower()
            self._attr_current_cover_position = percent
            self._attr_current_cover_tilt_position = percent
            self.async_write_ha_state()

    async def __update_current_cover_tilt_position(self) -> None:
        response: dict | None = await self._api.get_status(self.unique_id)
        if response is not None:
            position: int | None = response.get("slidePosition")
            if position is not None:
                self._attr_is_closed = position in [0, 100]
                if position > 50:
                    percent = 100 - ((position - 50) * 2)
                else:
                    percent = 100 - (50 - position) * 2
                self._attr_current_cover_position = percent
                self._attr_current_cover_tilt_position = percent


class SwitchBotCloudCoverRollerShade(SwitchBotCloudCover):
    """Representation of a SwitchBot Cover."""

    _attr_name = None
    _attr_is_closed: bool | None = None

    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
    )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(RollerShadeCommands.SET_POSITION, parameters=str(0))
        self._attr_current_cover_position = 100
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.send_api_command(
            RollerShadeCommands.SET_POSITION, parameters=str(100)
        )
        self._attr_current_cover_position = 0
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position: int | None = kwargs.get("position")
        if position is not None:
            await self.send_api_command(
                RollerShadeCommands.SET_POSITION, parameters=str(100 - position)
            )
            self._attr_current_cover_position = position
            self._attr_is_closed = position == 0
            self.async_write_ha_state()


def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> (
    SwitchBotCloudCoverTilt
    | SwitchBotCloudCoverRollerShade
    | SwitchBotCloudCoverCurtain
):
    """Make a SwitchBotCloudCover device."""
    if device.device_type == "Blind Tilt":
        return SwitchBotCloudCoverTilt(api, device, coordinator)
    if device.device_type == "Roller Shade":
        return SwitchBotCloudCoverRollerShade(api, device, coordinator)
    return SwitchBotCloudCoverCurtain(api, device, coordinator)
