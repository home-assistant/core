"""Support for the Switchbot Bot as a Cover."""

from typing import Any

from switchbot_api import CommonCommands, CurtainCommands, Device, Remote, SwitchBotAPI

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
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

    def _set_attributes(self) -> None:
        if self.coordinator.data is None:
            return
        position: int | None = (
            self.coordinator.data.get("slidePosition")
            if self.coordinator.data
            else None
        )
        if position is None:
            return
        position = self._convert_position_value(position)
        if position == 0:
            self._attr_is_closed = True
        else:
            self._attr_is_closed = False
        self.async_write_ha_state()

        self._attr_current_cover_position = position
        self._attr_current_cover_tilt_position = position

    def _convert_position_value(self, position: int) -> int:
        return 100 - position


class SwitchBotCloudCoverTilt(SwitchBotCloudCover):
    """Representation of a SwitchBot Cover."""

    _attr_name = None
    _attr_is_closed: bool | None = None

    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
        | CoverEntityFeature.STOP_TILT
    )


#
#     async def async_open_cover_tilt(self, **kwargs: Any) -> None:
#         """Open the cover."""
#         print("async_open_cover_tilt was call")
#         print(kwargs)
#
#     async def async_close_cover_tilt(self, **kwargs: Any) -> None:
#         """Close cover."""
#         print("async_close_cover_tilt was call")
#         print(kwargs)
#
#     async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
#         """Move the cover to a specific position."""
#         print("async_set_cover_tilt_position was call")
#         print(kwargs)
#
#     async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
#         """Stop the cover."""
#         print("async_stop_cover_tilt was call")
#         print(kwargs)
#
#     # def _set_attributes(self) -> None:
#     #     if self.coordinator.data is None:
#     #         return
#     #
#     #     self.current_cover_tilt_position = self.coordinator.data.get("SlidePosition")
#
#
#
class SwitchBotCloudCoverRollerShade(SwitchBotCloudCover):
    """Representation of a SwitchBot Cover."""

    _attr_name = None
    _attr_is_closed: bool | None = None

    _attr_supported_features: CoverEntityFeature = CoverEntityFeature.SET_POSITION


#     async def async_open_cover(self, **kwargs: Any) -> None:
#         """Open the cover."""
#         print("async_open_cover was call")
#         print(kwargs)
#         await self.send_api_command(CommonCommands.ON)
#         self._attr_is_closed = False
#         self.async_write_ha_state()
#
#     async def async_close_cover(self, **kwargs: Any) -> None:
#         """Close cover."""
#         model: str | None = self.device_info.get("model")
#         await self.send_api_command(CommonCommands.ON)
#         self._attr_is_closed = True
#         self.async_write_ha_state()
#
#     async def async_set_cover_position(self, **kwargs: Any) -> None:
#         """Move the cover to a specific position."""
#         print("async_set_cover_position was call")
#         print(kwargs)
#         position:int|None = kwargs.get("position")
#         if position is None:
#             return
#         model: str | None = self.device_info.get("model")
#         print("model",model)
#         if model and model in ["Roller Shade"]:
#             await self.send_api_command(RollerShadeCommands.SET_POSITION, parameters=str(position))
#         else:
#             await self.send_api_command(CurtainCommands.SET_POSITION, parameters=str(position))
#         self._attr_current_cover_position = position
#         self.async_write_ha_state()
#
#
#     async def async_stop_cover(self, **kwargs: Any) -> None:
#         """Stop the cover."""
#         print("async_stop_cover was call")
#         print(kwargs)
#         await self.send_api_command(CurtainCommands.PAUSE)
#
#     # def _set_attributes(self) -> None:
#     #     print("_set_attributes was call",self.coordinator.data)
#     #     if self.coordinator.data is None:
#     #         return
#     #     model: str | None = self.device_info.get("model")
#     #     if model and model in ["Roller Shade"]:
#     #         self._attr_supported_features: CoverEntityFeature = CoverEntityFeature.SET_POSITION
#     #
#     #     self._attr_current_cover_position = self.coordinator.data.get("SlidePosition")
#     #     print(self.current_cover_position)
#
#


class SwitchBotCloudCoverCurtain(SwitchBotCloudCover):
    """Representation of a SwitchBot Cover."""

    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(CommonCommands.ON)
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.send_api_command(CommonCommands.OFF)
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position: int | None = kwargs.get("position")
        if position is None:
            return
        await self.send_api_command(
            CurtainCommands.SET_POSITION,
            parameters=f"{0},ff,{self._convert_position_value(position)}",
        )
        self._attr_current_cover_position = position

        if position == 0:
            self._attr_is_closed = True
        else:
            self._attr_is_closed = None
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.send_api_command(CurtainCommands.PAUSE)
        response: dict | None = await self._api.get_status(self.unique_id)
        position: int | None = response.get("slidePosition") if response else None
        if position is None:
            return
        if position == 0:
            self._attr_is_closed = True
        else:
            self._attr_is_closed = None
        self.async_write_ha_state()


def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> (
    SwitchBotCloudCoverTilt
    | SwitchBotCloudCoverRollerShade
    | SwitchBotCloudCoverCurtain
):
    """Make a SwitchBotCloudCover device."""
    if device.device_type in ["Blind Tilt"]:
        return SwitchBotCloudCoverTilt(api, device, coordinator)
    if device.device_type in ["Roller Shade"]:
        return SwitchBotCloudCoverRollerShade(api, device, coordinator)
    return SwitchBotCloudCoverCurtain(api, device, coordinator)
