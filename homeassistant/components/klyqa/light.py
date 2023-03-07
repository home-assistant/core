"""Support for klyqa lights."""
from __future__ import annotations

from typing import Any, cast

from klyqa_ctl.account import AccountDevice
from klyqa_ctl.devices.light.commands import (
    BrightnessCommand,
    ColorCommand,
    PowerCommand,
    RequestCommand,
    RoutinePutCommand,
    RoutineStartCommand,
    TemperatureCommand,
)
from klyqa_ctl.devices.light.light import Light
from klyqa_ctl.devices.light.response_status import ResponseStatus
from klyqa_ctl.devices.light.scenes import SCENES as BULB_SCENES, get_scene_by_value
from klyqa_ctl.general.general import Command, Range, RgbColor, TypeJson, format_uid
from klyqa_ctl.general.message import Message, MessageState

from homeassistant.components.group.light import LightGroup
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ENTITY_ID_FORMAT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.area_registry import AreaEntry, AreaRegistry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify
import homeassistant.util.color as color_util
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from . import DOMAIN, LOGGER, KlyqaAccount, KlyqaEntity

SUPPORT_KLYQA: LightEntityFeature = LightEntityFeature.TRANSITION


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Async_setup_entry."""

    acc: KlyqaAccount = hass.data[DOMAIN].entries[entry.entry_id]
    if acc:
        await async_setup_klyqa(
            hass,
            ConfigType(entry.data),
            async_add_entities,
            entry=entry,
            acc=acc,
        )


async def async_setup_klyqa(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    acc: KlyqaAccount,
    discovery_info: DiscoveryInfoType | None = None,
    entry: ConfigEntry | None = None,
) -> None:
    """Set up the Klyqa Light platform."""

    entity_registry: EntityRegistry = er.async_get(hass)

    async def add_new_light_group(device_settings: dict) -> None:
        entity: KlyqaLightGroupEntity = KlyqaLightGroupEntity(hass, device_settings)

        add_entities([entity], True)

    async def add_new_light(u_id: str, acc_dev: AccountDevice) -> None:
        entity_id: str = ENTITY_ID_FORMAT.format(u_id)

        # Clear status added from cloud when the bulb is not connected to the
        # cloud so offline. Entity status will be updated when adding.
        if not acc_dev.device.cloud.connected:
            acc_dev.device.status = None

        registered_entity_id: str | None = entity_registry.async_get_entity_id(
            Platform.LIGHT, DOMAIN, u_id
        )

        if registered_entity_id and registered_entity_id != entity_id:
            entity_registry.async_remove(str(registered_entity_id))

        registered_entity_id = entity_registry.async_get_entity_id(
            Platform.LIGHT, DOMAIN, u_id
        )

        LOGGER.debug("Add entity %s (%s)", entity_id, acc_dev.acc_settings.get("name"))

        new_entity: KlyqaLightEntity = KlyqaLightEntity(
            acc_dev,
            acc,
            entity_id,
            should_poll=acc.polling,
            config_entry=entry,
        )
        if new_entity:
            hass.add_job(add_entities, [new_entity], True)

    acc.add_light_entity = add_new_light
    acc.add_light_group_entity = add_new_light_group

    await acc.update_account()

    return


class KlyqaLightGroupEntity(LightGroup):
    """Lightgroup."""

    def __init__(self, hass: HomeAssistant, settings: dict[Any, Any]) -> None:
        """Lightgroup."""
        self.hass = hass
        self.settings: TypeJson = settings

        u_id: str = format_uid(settings["id"])

        self.entity_id = ENTITY_ID_FORMAT.format(slugify(settings["id"]))

        entity_ids: list[str] = []

        for device in settings["devices"]:
            uid: str = format_uid(device["localDeviceId"])

            entity_ids.append(ENTITY_ID_FORMAT.format(uid))

        super().__init__(slugify(u_id), settings["name"], entity_ids, mode=None)


class KlyqaLightEntity(RestoreEntity, LightEntity, KlyqaEntity):
    """Representation of the Klyqa light."""

    _attr_supported_features: LightEntityFeature = SUPPORT_KLYQA
    _attr_transition_time: int = 500

    def __init__(
        self,
        acc_dev: AccountDevice,
        acc: KlyqaAccount,
        entity_id: str,
        should_poll: bool = True,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize a Klyqa Light Bulb."""

        super().__init__(
            acc_dev,
            acc,
            entity_id,
            should_poll=should_poll,
            config_entry=config_entry,
        )

        self._kq_light: Light = cast(Light, self._kq_dev)
        self._attr_device_class = "light"
        self._attr_icon = "mdi:lightbulb"
        self._attr_supported_color_modes: set[ColorMode] = set()
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_effect_list = []

        self.rooms: list[Any] = []

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        command: Command | None = None

        if ATTR_TRANSITION in kwargs:
            self._attr_transition_time = kwargs[ATTR_TRANSITION]

        if ATTR_HS_COLOR in kwargs:
            self._attr_rgb_color = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]

        if ATTR_RGB_COLOR in kwargs:
            self._attr_rgb_color = kwargs[ATTR_RGB_COLOR]

        if self._attr_rgb_color and (
            self._attr_rgb_color and ATTR_RGB_COLOR in kwargs or ATTR_HS_COLOR in kwargs
        ):
            command = ColorCommand(color=RgbColor(*self._attr_rgb_color))

        if ATTR_EFFECT in kwargs:
            msg: Message | None = await self.send(
                RoutinePutCommand.create(kwargs[ATTR_EFFECT], id_in_dev="0")
            )
            if msg and msg.state == MessageState.ANSWERED:
                await self.send(RoutineStartCommand(id="0"))

        if ATTR_COLOR_TEMP in kwargs:
            self._attr_color_temp = kwargs[ATTR_COLOR_TEMP]
            command = TemperatureCommand(
                temperature=(
                    color_temperature_mired_to_kelvin(self._attr_color_temp)
                    if self._attr_color_temp
                    else 0
                ),
            )

        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = int(kwargs[ATTR_BRIGHTNESS])
            command = BrightnessCommand(
                brightness=(round((self._attr_brightness / 255.0) * 100.0))
            )

        if ATTR_BRIGHTNESS_PCT in kwargs:
            self._attr_brightness = int(
                round((kwargs[ATTR_BRIGHTNESS_PCT] / 100) * 255)
            )
            command = BrightnessCommand(brightness=self._attr_brightness)
        if command:
            await self.send(command)
        else:
            await self.send(PowerCommand())

        await self.send(RequestCommand())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        cmd: PowerCommand = PowerCommand(status="off")
        self.hass.add_job(self.send, cmd)

    async def set_device_capabilities(self) -> None:
        """Set device color, temperature and scene capabilities."""

        if (
            self.device_config
            and "deviceTraits" in self.device_config
            and (device_traits := self.device_config["deviceTraits"])
        ):
            temp_range: Range | None = self._kq_light.temperature_range
            if temp_range and [  # look if device temp support and set limits
                x
                for x in device_traits
                if "msg_key" in x and x["msg_key"] == "temperature"
            ]:
                self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
                self._attr_max_color_temp_kelvin = (
                    temp_range.max if temp_range else 6500
                )
                self._attr_min_color_temp_kelvin = (
                    temp_range.min if temp_range else 2000
                )

            self._attr_supported_features |= LightEntityFeature.EFFECT

            if [  # look if device color support and set limits for color
                # and scenes
                x
                for x in device_traits
                if "msg_key" in x and x["msg_key"] == "color"
            ]:
                self._attr_supported_color_modes.add(ColorMode.RGB)
                self._attr_effect_list = [x["label"] for x in BULB_SCENES]
            else:
                self._attr_effect_list = [
                    x["label"] for x in BULB_SCENES if "cwww" in x
                ]

    async def async_update_settings(self) -> None:
        """Set device specific settings from the Klyqa settings cloud."""

        await super().async_update_settings()

        await self.set_device_capabilities()

        entity_registry: EntityRegistry = er.async_get(self.hass)
        entity_id: str | None = entity_registry.async_get_entity_id(
            Platform.LIGHT, DOMAIN, str(self.unique_id)
        )
        entity_registry_entry: RegistryEntry | None = None
        if entity_id:
            entity_registry_entry = entity_registry.async_get(str(entity_id))

        device_registry: dr.DeviceRegistry = dr.async_get(self.hass)

        device: dr.DeviceEntry | None = device_registry.async_get_device(
            identifiers={(DOMAIN, self._attr_unique_id)}
        )

        device_entry: dr.DeviceEntry | None = None

        if self._kq_acc.settings and "rooms" in self._kq_acc.settings:
            self.rooms = []
            room: TypeJson
            for room in self._kq_acc.settings["rooms"]:
                for dev in room["devices"]:
                    if dev and format_uid(dev["localDeviceId"]) == self.u_id:
                        self.rooms.append(room)

            if (
                entity_registry_entry
                and entity_registry_entry.area_id != ""
                and len(self.rooms) == 0
            ):
                entity_registry.async_update_entity(
                    entity_id=entity_registry_entry.entity_id, area_id=""
                )

            if (
                device_entry is not None
                and device is not None
                and device.area_id != ""
                and len(self.rooms) == 0
            ):
                device_registry.async_update_device(device_entry.id, area_id="")

            elif len(self.rooms) > 0:
                room_name: str = self.rooms[0]["name"]
                area_reg: AreaRegistry = ar.async_get(self.hass)
                # only 1 room supported per device by ha
                area: AreaEntry | None = area_reg.async_get_area_by_name(room_name)

                if not area:
                    self.hass.data[DOMAIN].entities_area_update.setdefault(
                        room_name, set()
                    ).add(self.entity_id)
                    # new area first add
                    LOGGER.debug("Create new room %s", room_name)
                    area = area_reg.async_get_or_create(room_name)
                    LOGGER.debug("Add bulb %s to new room %s", self.name, area.name)

                if area:
                    if device_entry is not None and entity_registry_entry:
                        device_registry.async_update_device(
                            device_entry.id,
                            area_id=entity_registry_entry.area_id,
                        )

                    if (
                        entity_registry_entry
                        and entity_registry_entry.area_id != area.id
                    ):
                        LOGGER.debug("Add bulb %s to room %s", self.name, area.name)
                        entity_registry.async_update_entity(
                            entity_id=entity_registry_entry.entity_id,
                            area_id=area.id,
                        )

    async def request_device_state(self) -> None:
        """Send device state request to device."""

        await self.send(RequestCommand(), time_to_live_secs=5)

    def update_device_state(self, state_complete: ResponseStatus | None) -> None:
        """Process state request response from the bulb to the entity state."""

        self._attr_assumed_state = True

        if not state_complete or not isinstance(state_complete, ResponseStatus):
            self._attr_is_on = False
            self._attr_assumed_state = False
            return

        if state_complete.type == "error":
            LOGGER.error(state_complete.type)
            return

        state_type: str = state_complete.type
        if not state_type or state_type != "status":
            return

        self._kq_dev.status = state_complete

        self._attr_color_temp = (
            color_temperature_kelvin_to_mired(float(state_complete.temperature))
            if state_complete.temperature
            else 0
        )
        if isinstance(state_complete.color, RgbColor):
            self._attr_rgb_color = (
                int(state_complete.color.r),
                int(state_complete.color.g),
                int(state_complete.color.b),
            )
            self._attr_hs_color = color_util.color_RGB_to_hs(*self._attr_rgb_color)

        self._attr_brightness = (
            int((float(state_complete.brightness) / 100) * 255)
            if state_complete.brightness is not None
            else None
        )

        self._attr_is_on = (
            isinstance(state_complete.status, list) and state_complete.status[0] == "on"
        ) or (isinstance(state_complete.status, str) and state_complete.status == "on")

        self._attr_color_mode = (
            ColorMode.COLOR_TEMP
            if state_complete.mode == "cct"
            else "effect"
            if state_complete.mode == "cmd"
            else state_complete.mode
        )
        self._attr_effect = ""
        if state_complete.mode == "cmd" and state_complete.active_scene is not None:
            scn: dict[str, Any] = get_scene_by_value(
                "id", int(state_complete.active_scene)
            )
            if scn:
                self._attr_effect = scn["label"]

        self._attr_assumed_state = False
        self.schedule_update_ha_state()
