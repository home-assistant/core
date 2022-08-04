"""Support for Aqara select."""
from __future__ import annotations
from dataclasses import dataclass

# from typing import cast

from aqara_iot import AqaraPoint, AqaraDeviceManager

# from aqara_iot.device import ValueRange

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantAqaraData
from .base import AqaraEntity, find_aqara_device_points_and_register
from .const import (
    DOMAIN,
    AQARA_DISCOVERY_NEW,
)


@dataclass
class AqaraSelectEntityDescription(SelectEntityDescription):
    """Describe an Aqara AqaraSelectEntityDescription entity."""

    selection: dict[str, str] | None = None


smart_pet_feeder = (
    # AqaraSelectEntityDescription(  # 0: 关闭 1: 打开
    #     key="4.21.85",
    #     name="开烘干",
    #     icon="mdi:numeric",
    #     entity_category=EntityCategory.CONFIG,
    #     selection={"open": "1", "close": "0"},
    # ),
)


SELECTS: dict[str, tuple[SelectEntityDescription, ...]] = {
    "aqara.tow_w.acn001": (
        AqaraSelectEntityDescription(  # 0: 关闭 1: 打开
            key="4.21.85",
            name="开烘干",
            icon="mdi:numeric",
            entity_category=EntityCategory.CONFIG,
            selection={"open": "1", "close": "0"},
        ),  # 智能毛巾架 H1
        AqaraSelectEntityDescription(  # 0: 关闭 1: 打开
            key="14.92.85",
            name="设置温度",
            icon="mdi:numeric",
            entity_category=EntityCategory.CONFIG,
            selection={
                "45": "45",
                "46": "46",
                "47": "47",
                "48": "48",
                "49": "49",
                "50": "50",
                "51": "51",
                "52": "52",
                "53": "53",
                "54": "54",
                "55": "55",
                "56": "56",
                "57": "57",
                "58": "58",
                "59": "59",
                "60": "60",
                "61": "61",
                "62": "62",
                "63": "63",
                "64": "64",
                "65": "65",
            },
        ),  # 智能毛巾架 H1 设置范围45-65℃，步长1，默认55℃
    ),
    "aqara.bed.hhcn03": (  # 智能电动床W1
        AqaraSelectEntityDescription(  # 背腿同降
            key="4.32.85",  # bool_switch_second
            name="背腿同降",
            icon="mdi:numeric",
            entity_category=EntityCategory.CONFIG,
            selection={"start": "1", "pause": "0"},
        ),
        AqaraSelectEntityDescription(  # 背腿同升
            key="4.31.85",  # bool_switch_first
            name="背腿同降",
            icon="mdi:numeric",
            entity_category=EntityCategory.CONFIG,
            selection={"start": "1", "pause": "0"},
        ),
        AqaraSelectEntityDescription(  # 模式
            key="14.47.85",  # 模式 14.47.85	 set_device_mode2
            name="模式",
            icon="mdi:numeric",
            entity_category=EntityCategory.CONFIG,
            selection={
                "sleep": 2,
                "lactation": 4,
                "zero pressure": 0,
                "Stop snoring": 5,
                "watch film": 3,
                "yoga": 1,
            },  # 2: 睡眠 4: 哺乳 0: 零压力 5: 止酣 3: 观影 1: 瑜伽
        ),
        AqaraSelectEntityDescription(  # 按摩
            key="14.8.85",  # set_mode
            name="按摩",
            icon="mdi:numeric",
            entity_category=EntityCategory.CONFIG,
            selection={
                "Stop": "0",
                "Continuous vibration massage": "1",
                "Intermittent pulse massage": "2",
                "Wave cushioning massage": "3",
            },
        ),
        AqaraSelectEntityDescription(  # 按摩
            key="14.35.85",  # set_mode
            name="按摩强度",
            icon="mdi:numeric",
            entity_category=EntityCategory.CONFIG,
            selection={
                "soft": "0",
                "middle": "1",
                "violent": "2",
            },
        ),
        AqaraSelectEntityDescription(  # 按摩定时
            key="14.48.85",  # set_device_mode3
            name="按摩定时",
            icon="mdi:numeric",
            entity_category=EntityCategory.CONFIG,
            selection={
                "10 min": "0",
                "20 min": "1",
                "30 min": "2",
            },
        ),
    ),
    # "aqara.feeder.acn001": #智能宠物喂食器C1
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Aqara select dynamically through Aqara discovery."""
    hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Aqara select."""
        entities: list[AqaraSelectEntity] = []

        def append_entity(aqara_point, description):
            entities.append(
                AqaraSelectEntity(aqara_point, hass_data.device_manager, description)
            )

        find_aqara_device_points_and_register(
            hass, entry.entry_id, hass_data, device_ids, SELECTS, append_entity
        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, AQARA_DISCOVERY_NEW, async_discover_device)
    )


class AqaraSelectEntity(AqaraEntity, SelectEntity):
    """Aqara Select Entity."""

    entity_description: AqaraSelectEntityDescription

    def __init__(
        self,
        point: AqaraPoint,
        device_manager: AqaraDeviceManager,
        description: AqaraSelectEntityDescription,
    ) -> None:
        """Init Aqara sensor."""
        super().__init__(point, device_manager)
        self.entity_description = description
        self._attr_options = list(description.selection.keys())

        # self._attr_opions: list[str] = description.selection.keys()

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        # Raw value
        point_value = self.point.get_value()
        for key, value in self.entity_description.selection.items():
            if value == point_value:
                return key
        return None

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        for key, value in self.entity_description.selection.items():
            if key == option:
                self._send_command([{self.point.resource_id: value}])
