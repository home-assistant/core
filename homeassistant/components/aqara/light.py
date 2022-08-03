"""Support for the Aqara lights."""
from __future__ import annotations

from dataclasses import dataclass
from pickle import TRUE, FALSE
from typing import Any
import copy
from aqara_iot import AqaraPoint, AqaraDeviceManager

from homeassistant.components.light import (
    # ATTR_BRIGHTNESS,
    # ATTR_COLOR_TEMP,
    # ATTR_HS_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_ONOFF,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from . import HomeAssistantAqaraData
from .base import AqaraEntity, find_aqara_device_points_and_register
from .const import DOMAIN, AQARA_DISCOVERY_NEW
from .const import (
    AQARA_HA_SIGNAL_UPDATE_ENTITY,
    DOMAIN,
)
from .base import (
    AqaraEntity,
    find_aqara_device_points_and_register,
)


@dataclass
class AqaraLightEntityDescription(LightEntityDescription):
    """Describe an Aqara light entity."""

    # default all support on/off
    color_model: COLOR_MODE_ONOFF | None = None

    # 灯模式，模式切换：0x00：level模式，0x01:色温模式， 0x02:RGB模式 （该设备不支持该资源值，模式由14.35.85上报）
    color_mode_res_id: str | None = None  # 如果color_model = None 就需要通过获取资源id获取

    on_off_res_id: str = "4.1.85"  # power_status

    # brightness: str | None = None #最小值: 0 最大值: 100 步长: 1 单位: 1
    brightness_res_id: str | None = "14.7.1006"
    brightness_max_res_id: str | None = ""
    brightness_min_res_id: str | None = ""

    rgbw_color_res_id: str | None = ""
    rgb_color_res_id: str | None = ""

    color_data: float | tuple[float, ...] | None = None

    # color temperature setting
    color_temp_res_id: str | None = ""
    coldest_color_temperature: int | None = 150
    warmest_color_temperature: int | None = 370

    on_value: str | None = "1"
    off_value: str | None = "0"

    def set_key(self, key: str) -> AqaraLightEntityDescription:
        self.key = key
        return self

    def set_color_mode_res_id(self, value: str) -> AqaraLightEntityDescription:
        self.color_mode_res_id = value
        return self

    def set_color_temp_res_id(self, value: str) -> AqaraLightEntityDescription:
        self.color_temp_res_id = value
        return self

    def set_on_value(self, value: str) -> AqaraLightEntityDescription:
        self.on_value = value
        return self

    def set_off_value(self, value: str) -> AqaraLightEntityDescription:
        self.off_value = value
        return self

    def set_brightness_res_id(self, value: str) -> AqaraLightEntityDescription:
        self.brightness_res_id = value
        return self

    def set_rgbw_color_res_id(self, value: str) -> AqaraLightEntityDescription:
        self.rgbw_color_res_id = value
        return self

    def set_rgb_color_res_id(self, value: str) -> AqaraLightEntityDescription:
        self.rgb_color_res_id = value
        return self

    def set_on_off_res_id(self, value: str) -> AqaraLightEntityDescription:
        self.on_off_res_id = value
        return self

    def set_coldest_color_temperature(self, value: int) -> AqaraLightEntityDescription:
        self.coldest_color_temperature = value
        return self

    def set_warmest_color_temperature(self, value: int) -> AqaraLightEntityDescription:
        self.warmest_color_temperature = value
        return self


common_downlight_desc = AqaraLightEntityDescription(  # 1:
    key="4.1.85",
    color_model=COLOR_MODE_RGBW,
    color_mode_res_id="14.35.85",
    on_off_res_id="4.1.85",
    name="brightness light",
    brightness_res_id="14.3.85",
    icon="mdi:",
    entity_category=EntityCategory.CONFIG,
)


# AqaraLightEntityDescription(
#     key="14.1.85",
#     name="亮度百分比",  # 最小值: 1 最大值: 100  步长: 单位:
#     brightness=DPCode.BRIGHT_VALUE_1,
#     brightness_max=DPCode.BRIGHTNESS_MAX_1,
#     brightness_min=DPCode.BRIGHTNESS_MIN_1,
#     # 开关状态  4.1.85
#     #不支持   灯模式 14.11.85    模式切换：0x00 level, 0x01:色温，02 RGB
#     色温值  14.2.85
#     #颜色模式 14.35.85   1: XY值模式 2: 色温模式 0: 颜色和饱和度
#     最冷色温 1.13.85
#     最暖色温 1.14.85
#     上电开灯色温 14.9.85
# ),

LIGHTS: dict[str, tuple[AqaraLightEntityDescription, ...]] = {
    "lumi.light.acn026": (common_downlight_desc,),  # 筒灯 T2
    "lumi.light.acn025": (common_downlight_desc,),  # 射灯 T2（36度）
    "lumi.light.acn024": (common_downlight_desc,),  # 射灯 T2（24度）
    "lumi.light.acn023": (common_downlight_desc,),  # 射灯 T2（15度）
    # "virtual.controller.a4acn6": (
    #     common_downlight.set_key("4.1.85")
    #     .set_color_mode_res_id("")
    #     .set_brightness_res_id("1.1.85")
    # ),  # 虚拟子设备-灯
    # "lumi.light.acn008": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("14.1.85")
    # ),  # 轨道格栅灯 H1（12头）
    # "lumi.light.acn012": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("14.1.85")
    # ),  # 轨道折叠格栅灯 H1（6头）
    # "lumi.light.acn011": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("14.1.85")
    # ),  # 轨道吊线灯 H1
    # "lumi.light.acn010": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("14.1.85")
    # ),  # 轨道泛光灯 H1（60cm）
    # "lumi.light.acn009": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("14.1.85")
    # ),  # 轨道泛光灯 H1（30cm）
    # "lumi.light.acn007": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("14.1.85")
    # ),  # 轨道格栅灯 H1（6头
    # "lumi.light.acn013": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("14.1.85")
    # ),  # 轨道偏光灯 H1
    # "lumi.light.acn006": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("14.1.85")
    # ),  # 轨道射灯 H1（24度）
    # "lumi.light.acn014": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("1.7.85")
    # ),  # Aqara LED灯泡 T1（可调色温）
    # "lumi.light.acn003": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("1.7.85")
    # ),  # Aqara吸顶灯L1-350
    # "virtual.controller.a4acn3": (
    #     common_downlight.set_key("4.1.85").set_brightness_res_id("1.1.85"),
    #     common_downlight.set_key("4.2.85").set_brightness_res_id("1.1.85"),
    # ),  # 虚拟设备-灯
    # "app.group.temperature": (
    #     common_downlight.set_key("4.1.85")
    #     .set_brightness_res_id("1.1.85")
    #     .set_color_temp_res_id("1.4.85"),
    # ),  # 色温灯组
    # "app.group.color": (
    #     copy.copy(common_downlight).set_key("4.1.85")
    #     .set_brightness_res_id("1.1.85")
    #     .set_color_temp_res_id("1.4.85"),
    # ),  # 彩灯组
    # "lumi.light.cwac02": (
    #     copy.copy(common_downlight).set_key("4.1.85")
    #     .set_brightness_res_id("1.7.85")
    #     .set_color_temp_res_id("1.9.85"),
    # ),  # Aqara LED灯泡 T1 (可调色温)
    # "miot.light.philips_downlight": (
    #     copy.copy(common_downlight).set_key("4.1.85")
    #     .set_brightness_res_id("14.1.85")
    #     .set_color_temp_res_id("14.6.85"),
    # ),  # 飞利浦智睿筒灯
    # "miot.light.philips_bulb": (
    #     copy.copy(common_downlight).set_key("4.1.85")
    #     .set_brightness_res_id("14.1.85")
    #     .set_color_temp_res_id("14.3.85"),  # 最小值: 3000 最大值: 5700
    # ),  # 飞利浦智睿球泡灯
    # "miot.light.philips_zystrip": (
    #     copy.copy(common_downlight).set_key("4.1.85")
    #     .set_brightness_res_id("14.1.85")
    #     .set_color_temp_res_id(""),
    # ),  # 飞利浦智奕灯带
    # # "virtual.ir.light": (common_downlight),  # 灯泡
    # "miot.light.ceiling1": (
    #     copy.copy(common_downlight).set_key("4.1.85")
    #     .set_brightness_res_id("14.1.85")
    #     .set_color_temp_res_id("14.3.85")
    # ),  # 米家LED吸顶灯(yeelink.light.ceiling1)
    # "miot.light.strip2": (
    #     copy.copy(common_downlight).set_key("4.1.85")
    #     .set_brightness_res_id("14.1.85")
    #     .set_color_temp_res_id("14.3.85")
    # ),  # Yeelight智能彩光灯带(可延长版)
    # "miot.light.lamp1": (
    #     copy.copy(common_downlight).set_key("4.1.85")
    #     .set_brightness_res_id("14.1.85")
    #     .set_color_temp_res_id("14.3.85")
    # ),  # 米家 LED 智能台灯
    # "miot.light.strip1": (
    #     copy.copy(common_downlight).set_key("4.1.85")
    #     .set_brightness_res_id("14.1.85")
    #     .set_color_temp_res_id("14.3.85")
    # ),  # 米家智能彩光灯带(
    # "miot.light.ceiling5": (
    #     copy.copy(common_downlight_desc).set_key("4.1.85")
    #     .set_brightness_res_id("14.1.85")
    #     .set_color_temp_res_id("14.3.85")
    # ),  # 米家LED吸顶灯
    # "lumi.light.cwjwcn01": (
    #     copy.copy(common_downlight_desc).set_key("4.1.85")
    #     .set_brightness_res_id("14.1.85")
    #     .set_color_temp_res_id("14.2.85")
    # ),  # 射灯（可调色温）
    # Aqara智能调光模块 T1
    "lumi.light.rgbac1": (
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_on_off_res_id("4.1.85")
        .set_color_temp_res_id("14.2.85")
        .set_brightness_res_id("14.1.85"),
    ),  # Aqara智能恒流驱动器
    "lumi.light.cbacn1": (
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_on_off_res_id("4.1.85")
        .set_brightness_res_id("14.1.85"),
    ),
    "lumi.gateway.aqhm02": (
        copy.copy(common_downlight_desc)
        .set_brightness_res_id("14.7.1006")
        .set_on_off_res_id("14.7.111")
        .set_rgb_color_res_id("14.7.85")
        .set_key("14.7.111"),
    ),  # lumi.gateway.acn01 m1s 国内版本
    "lumi.gateway.acn01": (
        copy.copy(common_downlight_desc)
        .set_brightness_res_id("14.7.1006")
        .set_key("14.7.111")
        .set_rgb_color_res_id("14.7.85")
        .set_on_off_res_id("14.7.111"),
    ),  # 智能LED灯泡（可调色温&亮度)
    "lumi.light.aqcn02": (
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_on_off_res_id("4.1.85")
        .set_brightness_res_id("14.1.85")
        .set_coldest_color_temperature(153)
        .set_warmest_color_temperature(370)
        .set_color_temp_res_id("14.2.85"),
    ),
    "lumi.light.cwopcn03": (  # 吸顶灯MX480（可调色温）
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_brightness_res_id("14.1.85")
        .set_color_temp_res_id("14.2.85")
        .set_coldest_color_temperature(175)
        .set_warmest_color_temperature(370),
    ),
    "lumi.light.cwopcn02": (  # 吸顶灯MX650（可调色温）
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_brightness_res_id("14.1.85")
        .set_color_temp_res_id("14.2.85")
        .set_coldest_color_temperature(175)
        .set_warmest_color_temperature(370),
    ),
    "lumi.light.cwopcn01": (  # 吸顶灯MX960（可调色温）
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_brightness_res_id("14.1.85")
        .set_color_temp_res_id("14.2.85")
        .set_coldest_color_temperature(175)
        .set_warmest_color_temperature(370),
    ),
    "lumi.light.abr01": (  # 宽电压LED灯泡（可调亮度）
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_brightness_res_id("14.1.85"),
        # .set_color_temp_res_id("14.2.85")
        # .set_coldest_color_temperature(175)
        # .set_warmest_color_temperature(370),
    ),
    "lumi.light.acn015": (  # Aqara光艺晴空灯 H1
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_brightness_res_id("1.7.85")
        .set_color_temp_res_id("1.9.85")
        .set_coldest_color_temperature(153)
        .set_warmest_color_temperature(370),
    ),
    "lumi.light.wjwcn01": (  # 射灯（可调亮度）
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_brightness_res_id("14.1.85")
        .set_color_temp_res_id("14.2.85")
        .set_coldest_color_temperature(0)
        .set_warmest_color_temperature(65535),
    ),
    "lumi.light.cwjwcn02": (  # 筒灯（可调色温）
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_brightness_res_id("14.1.85")
        .set_color_temp_res_id("14.2.85"),
    ),
    "lumi.light.cwac02": (  # Aqara LED灯泡 T1 (可调色温)
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_brightness_res_id("1.7.85")
        .set_color_temp_res_id("1.9.85"),
    ),
    "lumi.dimmer.rcbac1": (  # Aqara智能灯带驱动模块
        copy.copy(common_downlight_desc)
        .set_key("4.1.85")
        .set_brightness_res_id("14.1.85")
        .set_color_temp_res_id("14.2.85"),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up aqara light dynamically through aqara discovery."""
    hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]):
        """Discover and add a discovered aqara light."""
        entities: list[AqaraLightEntity] = []

        def append_entity(
            aqara_point: AqaraPoint, description: AqaraLightEntityDescription
        ):

            entity: AqaraLightEntity = AqaraLightEntity(
                aqara_point, hass_data.device_manager, description
            )
            entities.append(entity)

            async_dispatcher_connect(
                hass,
                f"{AQARA_HA_SIGNAL_UPDATE_ENTITY}_{aqara_point.did}",
                entity.async_update_attr,
            )

        find_aqara_device_points_and_register(
            hass, entry.entry_id, hass_data, device_ids, LIGHTS, append_entity
        )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, AQARA_DISCOVERY_NEW, async_discover_device)
    )


def rgb_to_argb(rgb: tuple[int, int, int]) -> str:
    argb = 0 << 24 | round(rgb[0]) << 16 | round(rgb[1]) << 8 | round(rgb[2])
    return argb


def rgbw_to_argb(rgb: tuple[int, int, int, int]) -> str:
    argb = (
        round(rgb[3]) << 24 | round(rgb[0]) << 16 | round(rgb[1]) << 8 | round(rgb[2])
    )
    return argb


class AqaraLightEntity(AqaraEntity, LightEntity):
    """Aqara light device."""

    entity_description: AqaraLightEntityDescription

    def __init__(
        self,
        point: AqaraPoint,
        device_manager: AqaraDeviceManager,
        description: AqaraLightEntityDescription,
    ) -> None:
        """Init AqaraHaLight."""
        super().__init__(point, device_manager)
        self.entity_description = description
        self._attr_supported_color_modes = {COLOR_MODE_ONOFF}

        if len(self.entity_description.rgbw_color_res_id) != 0:
            self._attr_supported_color_modes.add(COLOR_MODE_RGBW)

        if len(self.entity_description.rgb_color_res_id) != 0:
            self._attr_supported_color_modes.add(COLOR_MODE_RGB)

        if len(self.entity_description.color_temp_res_id) != 0:
            self._attr_supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
            self._attr_min_mireds = self.entity_description.coldest_color_temperature
            self._attr_max_mireds = self.entity_description.warmest_color_temperature

        if len(self.entity_description.brightness_res_id) != 0:
            self._attr_supported_color_modes.add(COLOR_MODE_BRIGHTNESS)

    async def async_update_attr(self, point: AqaraPoint) -> None:

        if point.resource_id == self.entity_description.brightness_res_id:
            brightness: float = int(point.value) * 255 / 100
            self._attr_brightness = round(brightness)
            if self._attr_brightness == 0:
                self._attr_is_on = FALSE

        elif point.resource_id == self.entity_description.color_temp_res_id:
            self._attr_color_temp = point.value
        elif point.resource_id == self.entity_description.on_off_res_id:
            if self.entity_description.on_value == point.value:
                self._attr_is_on = TRUE
            else:
                self._attr_is_on = FALSE

        self._async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""

        value = self.device_manager.get_point_value(
            self.point.did, self.entity_description.on_off_res_id
        )

        return value == self.entity_description.on_value

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        # if COLOR_MODE_BRIGHTNESS not in self._attr_supported_color_modes:
        #     return None

        return self._attr_brightness

    @property
    def color_temp(self) -> int | None:
        """Return the color_temp of the light."""
        # if COLOR_MODE_COLOR_TEMP not in self._attr_supported_color_modes:
        #     return None

        temperature = self.device_manager.get_point_value(
            self.point.did, self.entity_description.color_temp_res_id
        )
        if temperature == "":
            return None

        return round(int(temperature))

    def turn_on(self, **kwargs: Any) -> None:

        """Turn on or control the light."""
        if kwargs.get("brightness") is not None:
            commands = [
                {
                    self.entity_description.brightness_res_id: round(
                        kwargs.get("brightness") * 100 / 255
                    )
                }
            ]
        elif kwargs.get("rgbw_color") is not None:

            rgbw: tuple[int, int, int, int] = kwargs.get("rgbw_color")
            argb = rgbw_to_argb(rgbw)
            commands = [{self.entity_description.rgbw_color_res_id: argb}]
        elif kwargs.get("rgb_color") is not None:

            rgb: tuple[int, int, int] = kwargs.get("rgb_color")
            argb = rgb_to_argb(rgb)
            commands = [{self.entity_description.rgb_color_res_id: argb}]
        elif kwargs.get("color_temp") is not None:

            color_temp = kwargs.get("color_temp")
            commands = [{self.entity_description.color_temp_res_id: color_temp}]
        else:
            commands = [
                {
                    self.entity_description.on_off_res_id: self.entity_description.on_value
                }
            ]

        self._send_command(commands)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        commands = [
            {self.entity_description.on_off_res_id: self.entity_description.off_value}
        ]
        self._send_command(commands)
