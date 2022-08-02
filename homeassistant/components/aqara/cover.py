"""Support for Aqara Cover."""
from __future__ import annotations

from dataclasses import dataclass
import logging

# from multiprocessing import set_forkserver_preload
from typing import Any
from aqara_iot import AqaraPoint, AqaraDeviceManager
import functools as ft
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    # SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    # SUPPORT_OPEN_TILT,
    # SUPPORT_CLOSE_TILT,
    # SUPPORT_STOP_TILT,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import HomeAssistantAqaraData
from .base import (
    # EnumTypeData,
    IntegerTypeData,
    AqaraEntity,
    find_aqara_device_points_and_register,
    entity_data_update_binding,
)
from .const import DOMAIN, AQARA_DISCOVERY_NEW

_LOGGER = logging.getLogger(__name__)


@dataclass
class AqaraCoverEntityDescription(CoverEntityDescription):
    """Describe an Aqara cover entity."""

    current_position_percentage_res_id: str | None = None  # 当前百分比 [0,100]
    curtain_open_percentage_res_id: str | None = None  # 打开窗帘百分比 打开窗帘百分比，范围【0，100】
    set_mode_res_id: str | None = None  # 窗帘开关控制 0:开，1:关，2:停，3：自动auto
    # curtain_running_status_res_id: str | None = (
    #     None  # 运行状态 0: offing 1: oning 2: stop 3: hinder_stop"遇阻停止
    # )
    curtain_direct_res_id: str | None = None  # 窗帘的方向属性 1: 左开 2: 右开 3: 两边开 4卷帘，5柔纱帘，6百叶帘，7香格里拉帘，8斑马帘，9垂直百叶帘（左开），10垂直百叶帘（右开）
    supported_features: int = 0
    # def set_key(self, key: str) -> AqaraCoverEntityDescription:
    #     self.key = key

    # def set_current_position_percentage_res_id(
    #     self, res_id: str
    # ) -> AqaraCoverEntityDescription:
    #     self.current_position_percentage_res_id = res_id

    # def set_curtain_open_percentage_res_id(
    #     self, id: str
    # ) -> AqaraCoverEntityDescription:
    #     self.curtain_open_percentage_res_id = id

    # def set_set_mode_res_id(self, res_id: str) -> AqaraCoverEntityDescription:
    #     self.set_mode_res_id = res_id

    # # def set_curtain_running_status_res_id(
    # #     self, res_id: str
    # # ) -> AqaraCoverEntityDescription:
    # #     self.curtain_running_status_res_id = res_id

    # def set_curtain_direct_res_id(self, res_id: str) -> AqaraCoverEntityDescription:
    #     self.curtain_direct_res_id = res_id


curtain = AqaraCoverEntityDescription(
    key="0.55.85",
    name="Curtain",
    current_position_percentage_res_id="0.55.85",
    curtain_open_percentage_res_id="1.1.85",
    set_mode_res_id="14.8.85",  # # 窗帘开关控制 0:开，1:关，2:停，3：自动auto
    # curtain_running_status_res_id="14.4.85",
    curtain_direct_res_id="8.0.8112",
    supported_features=SUPPORT_OPEN
    | SUPPORT_CLOSE
    | SUPPORT_SET_POSITION
    | SUPPORT_STOP,
    device_class=CoverDeviceClass.CURTAIN,
)
curtain_type2 = AqaraCoverEntityDescription(
    key="1.1.85",
    name="Curtain",
    current_position_percentage_res_id="1.1.85",
    curtain_open_percentage_res_id="1.1.85",
    set_mode_res_id="14.2.85",  # # 窗帘开关控制 0:开，1:关，2:停，3：自动auto
    # curtain_running_status_res_id="14.4.85",
    curtain_direct_res_id="8.0.8112",
    supported_features=SUPPORT_OPEN
    | SUPPORT_CLOSE
    | SUPPORT_SET_POSITION
    | SUPPORT_STOP,
    device_class=CoverDeviceClass.CURTAIN,
)

curtain_type3 = AqaraCoverEntityDescription(
    key="1.5.85",
    name="Curtain",
    current_position_percentage_res_id="1.5.85",
    curtain_open_percentage_res_id="1.5.85",
    set_mode_res_id="14.1.85",  # # 窗帘开关控制 0:开，1:关，2:停，3：自动auto
    curtain_direct_res_id="8.0.8112",
    supported_features=SUPPORT_OPEN
    | SUPPORT_CLOSE
    | SUPPORT_SET_POSITION
    | SUPPORT_STOP,
    device_class=CoverDeviceClass.CURTAIN,
)


curtain_roller = AqaraCoverEntityDescription(
    key="1.1.85",
    name="Curtain",
    current_position_percentage_res_id="1.1.85",
    curtain_open_percentage_res_id="1.1.85",
    set_mode_res_id="14.8.85",  # # 窗帘开关控制 0:开，1:关，2:停，3：自动auto
    # curtain_running_status_res_id="14.4.85",
    curtain_direct_res_id="8.0.8112",  # (云端存储用户设置的属性)窗帘的方向属性，1左开，2右开，3两边开，4卷帘，5柔纱帘，6百叶帘，7香格里拉帘，8斑马帘，9垂直百叶帘（左开），10垂直百叶帘（右开）
    supported_features=SUPPORT_OPEN
    | SUPPORT_CLOSE
    | SUPPORT_SET_POSITION
    | SUPPORT_STOP,
    device_class=CoverDeviceClass.BLIND,
)
#   self._attr_supported_features = (
#         SUPPORT_OPEN
#         | SUPPORT_CLOSE
#         | SUPPORT_SET_POSITION
#         | SUPPORT_STOP
#         # | SUPPORT_OPEN_TILT
#         # | SUPPORT_CLOSE_TILT
#         # | SUPPORT_STOP_TILT
#         # | SUPPORT_SET_TILT_POSITION
#     )

COVERS: dict[str, tuple[AqaraCoverEntityDescription, ...]] = {
    # Curtain
    "lumi.curtain.agl001": (curtain,),  # 智能窗帘伴侣E1海外版
    "lumi.curtain.acn003": (curtain,),  # lumi.curtain.acn003
    "lumi.curtain.acn007": (curtain_type2,),  # Aqara智能窗帘电机（zigbee开合帘升级
    "lumi.curtain.acn004": (curtain_type2,),  # Aqara智能窗帘电机 X1
    "app.group.curtain": (curtain_type3,),  # 开合帘组
    "lumi.curtain.hagl08": (curtain_type2,),  # Aqara智能窗帘电机 A1
    "lumi.curtain.vagl02": (curtain_type2,),  # Aqara智能窗帘电机T1
    "lumi.curtain.hagl07": (curtain_type2,),  # 智能窗帘电机 C2
    "lumi.curtain.hagl06": (curtain_type2,),  # Aqara智能窗帘电机 B1S
    "lumi.curtain.hagl04": (curtain_type2,),  # Aqara智能窗帘电机（锂电池开合帘版)
    "lumi.curtain.es1": (curtain_type2,),  # 智能窗帘
    "lumi.curtain.v1": (curtain_type2,),  # 智能窗帘电机 (Zigbee开合帘版)
    # roller blind
    "lumi.curtain.acn002": (curtain_roller,),  # 智能卷帘伴侣海外版
    "app.group.roller": (curtain_type3,),  # 卷帘组
    "lumi.curtain.vakr01": (curtain_type2,),  # 卷帘电机 韩国版
    "lumi.curtain.aq2": (curtain_type2,),  # 卷帘电机
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Aqara cover dynamically through Aqara discovery."""
    hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered aqara cover."""
        entities: list[AqaraCoverEntity] = []

        def append_entity(aqara_point, description):
            entity = AqaraCoverEntity(
                aqara_point, hass_data.device_manager, description
            )
            entities.append(entity)
            res_ids: list[str] = [
                description.current_position_percentage_res_id,
                description.curtain_open_percentage_res_id,
                description.set_mode_res_id,
                description.curtain_direct_res_id,
            ]
            entity_data_update_binding(
                hass, hass_data, entity, aqara_point.did, res_ids
            )

        find_aqara_device_points_and_register(
            hass, entry.entry_id, hass_data, device_ids, COVERS, append_entity
        )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, AQARA_DISCOVERY_NEW, async_discover_device)
    )


class AqaraCoverEntity(AqaraEntity, CoverEntity):
    """Aqara Cover Device."""

    entity_description: AqaraCoverEntityDescription

    def __init__(
        self,
        point: AqaraPoint,
        device_manager: AqaraDeviceManager,
        description: AqaraCoverEntityDescription,
    ) -> None:
        """Init Aqara Cover."""
        super().__init__(point, device_manager)
        self.entity_description = description
        self._attr_supported_features = description.supported_features

        self._set_position_type = IntegerTypeData(
            min=0, max=100, scale=1, step=1, type="Int"
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return cover current position."""
        value = self.device_manager.get_point_value(
            self.point.did,
            self.entity_description.curtain_open_percentage_res_id,  # current_position_percentage_res_id
        )
        if value == "":
            return None
        return int(value)

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        position = self.device_manager.get_point_value(
            self.point.did, self.entity_description.current_position_percentage_res_id
        )
        return position == "0"

    def toggle(self, **kwargs: Any) -> None:
        self._send_command([{self.entity_description.set_mode_res_id: "3"}])  #

    async def async_toggle(self, **kwargs):
        """toggle the cover."""
        await self.hass.async_add_executor_job(ft.partial(self.toggle, **kwargs))

    def open_cover(self, **kwargs: Any) -> None:  # 窗帘开关控制 0:开，1:关，2:停，3：自动auto
        """Open the cover."""
        self._send_command([{self.entity_description.set_mode_res_id: "1"}])  #

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._send_command([{self.entity_description.set_mode_res_id: "0"}])  #

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._send_command([{self.entity_description.set_mode_res_id: "2"}])

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        self._send_command(
            [
                {
                    self.entity_description.curtain_open_percentage_res_id: str(
                        round(
                            self._set_position_type.remap_value_from(
                                kwargs[ATTR_POSITION], 0, 100, reverse=False
                            )
                        )
                    )
                }
            ]
        )

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        self._send_command(
            [
                {
                    self.entity_description.curtain_open_percentage_res_id: str(
                        round(
                            self._set_position_type.remap_value_from(
                                kwargs[ATTR_TILT_POSITION], 0, 100, reverse=False
                            )
                        )
                    )
                }
            ]
        )
