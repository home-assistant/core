"""Support for Aqara locks."""

from __future__ import annotations
from dataclasses import dataclass
from html import entities
from typing import Any
from aqara_iot import AqaraDeviceManager, AqaraPoint
from homeassistant.components.lock import LockEntity
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_LOCKED,
    STATE_UNLOCKED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later


from homeassistant.components.lock import LockEntity, LockEntityDescription

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantAqaraData
from .base import (
    AqaraEntity,
    find_aqara_device_points_and_register,
    entity_data_update_binding,
    entity_point_value_update_binding,
)
from .const import (
    AQARA_DISCOVERY_NEW,
    AQARA_HA_SIGNAL_UPDATE_ENTITY,
    DOMAIN,
    LOGGER,
    AQARA_BATTERY_LOW_ENTITY_NEW,
)
from .util import string_dot_to_underline


@dataclass
class AqaraLockEntityDescription(LockEntityDescription):
    """Describe an Aqara climate entity."""

    supported_features: int = 0

    # 4: 撬门 5: 门虚掩 1: 门已关 6: 其它 0: 门已开 7: 其它2 2: 超时未关 3: 敲门
    door_event_push_res_id: str | None = None  # 门事件推送 13.19.85
    low_battery_power_res_id: str | None = None  # 8.0.9001 低电压报警
    lock_event_res_id: str | None = None  # 门锁上锁事件 13.31.85

    user_id_manual_res_id: str | None = None  # 室内开门用户id 13.41.85
    user_id_fingerprint_res_id: str | None = None  # 指纹开门用户id 13.42.85
    user_id_password_res_id: str | None = None  # 密码开门用户id 13.43.85
    user_id_nfc_res_id: str | None = None  # NFC开门用户id 13.44.85
    user_id_ble_homekit_res_id: str | None = None  # HomtKit蓝牙开门用户id 13.45.85
    user_id_temporary_password_res_id: str | None = None  # 临时密码开门用户id 13.46.85
    user_id_manual_with_armed_res_id: str | None = None  # 离家模式下室内开门用户id 13.49.85
    lockout_event_res_id: str | None = None  # 门锁反锁事件 13.33.85
    door_event_res_id: str | None = (
        None  #  门事件 13.17.85  4: 撬门 5: 门虚掩 1: 门已关 6: 其它 0: 门已开 7: 其它2  2: 超时未关 3: 敲门
    )
    open_door_method_id_res_id: str | None = None  #  室外开门方式 13.18.85 0: 指纹开门 4: 临时密码开门 5: 钥匙开门 3: 蓝牙开门 2: NFC开门 1: 永久密码开门 15: 任意方式室外开门
    lock_state_res_id: str | None = None  # 门锁状态 13.88.85
    low_power_battery_res_id: str | None = (
        None  #   门锁低电压报警 13.89.85	0: 电池0低电量 1: 电池1低电量 2: 电池2低电量 ...
    )

    def set_key(self, key: str) -> LockEntityDescription:
        """Set key."""
        self.key = key
        return self


aqara_lock_n200 = AqaraLockEntityDescription(
    key="13.88.85",
    door_event_push_res_id="13.19.85",
    # low_battery_power_res_id="8.0.9001",
    lock_event_res_id="13.31.85",
    user_id_manual_res_id="13.41.85",
    user_id_fingerprint_res_id="13.42.85",
    user_id_password_res_id="13.43.85",
    user_id_nfc_res_id="13.44.85",
    user_id_ble_homekit_res_id="13.45.85",
    user_id_temporary_password_res_id="13.46.85",
    user_id_manual_with_armed_res_id="13.49.85",
    lockout_event_res_id="13.33.85",
    door_event_res_id="13.17.85",  #  4: 撬门 5: 门虚掩 1: 门已关 6: 其它 0: 门已开 7: 其它2  2: 超时未关 3: 敲门
    open_door_method_id_res_id="13.18.85",  # 0: 指纹开门 4: 临时密码开门 5: 钥匙开门 3: 蓝牙开门 2: NFC开门 1: 永久密码开门 15: 任意方式室外开门
    lock_state_res_id="13.88.85",
    low_power_battery_res_id="13.89.85",  # 0: 电池0低电量 1: 电池1低电量 2: 电池2低电量 ...
    # supported_features=SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE,
)


aqara_p100_lock = AqaraLockEntityDescription(
    key="13.20.85",
    # door_event_push_res_id="13.19.85",
    low_battery_power_res_id="8.0.9001",
    lock_event_res_id="13.10.85",
    user_id_manual_res_id="13.1.85",
    user_id_fingerprint_res_id="13.2.85",
    user_id_password_res_id="13.3.85",
    user_id_nfc_res_id="13.4.85",
    user_id_ble_homekit_res_id="13.5.85",
    user_id_temporary_password_res_id="13.6.85",
    user_id_manual_with_armed_res_id="13.7.85",  # 钥匙开门用户id   13.7.85	 user_id_key
    # lockout_event_res_id="13.11.85",
    door_event_res_id="13.20.85",  #  4: 撬门 5: 门虚掩 1: 门已关 6: 其它 0: 门已开 7: 其它2  2: 超时未关 3: 敲门    门状态事件  door_state_event
    open_door_method_id_res_id="13.15.85",  # 0: 指纹开门 4: 临时密码开门 5: 钥匙开门 3: 蓝牙开门 2: NFC开门 1: 永久密码开门 15: 任意方式室外开门
    lock_state_res_id="13.20.85",  # door_state_event
    # low_power_battery_res_id="13.89.85",  # 0: 电池0低电量 1: 电池1低电量 2: 电池2低电量 ...
    # supported_features=SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE,
)


s2_pro_lock = AqaraLockEntityDescription(
    key="13.26.85",
    # door_event_push_res_id="13.19.85",
    # low_battery_power_res_id="8.0.9001",
    # lock_event_res_id="13.10.85",
    # user_id_manual_res_id="13.1.85",
    # user_id_fingerprint_res_id="13.2.85",
    # user_id_password_res_id="13.3.85",
    # user_id_nfc_res_id="13.4.85",
    # user_id_ble_homekit_res_id="13.5.85",
    # user_id_temporary_password_res_id="13.6.85",
    # user_id_manual_with_armed_res_id="13.7.85",  # 钥匙开门用户id   13.7.85	 user_id_key
    # lockout_event_res_id="13.11.85",
    # door_event_res_id="13.20.85",  #  4: 撬门 5: 门虚掩 1: 门已关 6: 其它 0: 门已开 7: 其它2  2: 超时未关 3: 敲门    门状态事件  door_state_event
    # open_door_method_id_res_id="13.15.85",  # 0: 指纹开门 4: 临时密码开门 5: 钥匙开门 3: 蓝牙开门 2: NFC开门 1: 永久密码开门 15: 任意方式室外开门
    lock_state_res_id="13.26.85",  # door_state_event
    # low_power_battery_res_id="13.89.85",  # 0: 电池0低电量 1: 电池1低电量 2: 电池2低电量 ...
    # supported_features=SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE,
)


LOCK_DESCRIPTIONS: dict[str, tuple[AqaraLockEntityDescription, ...]] = {
    # "aqara.lock.acn008": (aqara_lock_n200,),  # Aqara智能门锁N200
    # "aqara.lock.acn004": (aqara_lock,),  # 人脸识别智能门锁D200
    # "lumi.lock.acn006": (aqara_lock,),  # 智能门RD1
    # "aqara.lock.acn003": (aqara_lock,),  # Aqara 智能门锁 A100（酒店专供版）
    # "aqara.lock.agl002": (aqara_lock,),  # 智能门锁A100海外版
    # "aqara.lock.acn002": (aqara_lock,),  # Aqara智能猫眼锁 S100
    # "aqara.lock.acn001": (aqara_lock,),  # Aqara 智能门锁 A100（苹果版）
    # "aqara.lock.aqgl01": (aqara_lock,),  # 全自动智能锁 D100 海外版
    # "aqara.lock.aqcn01": (aqara_lock,),  # 智能门锁 X10
    # "aqara.lock.eicn03": (aqara_lock,),  # EigenStone 智能门锁 J1
    # "aqara.lock.eicn01": (aqara_lock,),  # Aqara 智能门锁 A100
    # "aqara.lock.agcn01": (aqara_lock,),  # 海贝斯智能门锁
    # "aqara.lock.dacn03": (aqara_lock,),  # 全自动智能猫眼锁 H100
    # "aqara.lock.bzacn3": (aqara_lock,),  # 智能门锁N100
    # "aqara.lock.bzacn4": (aqara_lock,),  # N100智能门锁（全球通用）
    # "aqara.lock.dacn02": (aqara_lock,),  # Aqara智能门锁DZ1L
    # "aqara.lock.dacn01": (aqara_lock,),  # Aqara 智能门锁DF1
    "aqara.lock.wbzac1": (aqara_p100_lock,),  # 智能门锁 P100
    # "aqara.lock.zeecn1": (aqara_lock,),  # 科裕酒店门锁
    # "lumi.lock.acn04": (aqara_p100_lock,),  # 智能门锁 HL
    # "lumi.lock.acn05": (aqara_lock,),  # Aqara智能门锁S2 Pro-B
    # "lumi.lock.acn03": (s2_pro_lock,),  # Aqara 智能门锁S2 PRO
    # "lumi.lock.acn02": (aqara_lock,),  # Aqara智能门锁S2
    # "lumi.lock.aq1": (aqara_lock,),  # Aqara智能门锁
    # "lumi.ctrl_doorlock.es1": (aqara_lock,),  # 智能锁(海图克)
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Aqara climate dynamically through Aqara discovery."""
    hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Aqara climate."""
        entities: list[AqaraLockEntity] = []

        def add_lock_power_entity(self):
            for entity in entities:
                if entity.entity_description.low_battery_power_res_id is not None:
                    dispatcher_send(  # 先更新值.
                        hass,
                        AQARA_BATTERY_LOW_ENTITY_NEW,
                        entity.point.did,
                        entity.entity_description.low_battery_power_res_id,
                    )

        def append_entity(aqara_point, description: AqaraLockEntityDescription):
            entity = AqaraLockEntity(aqara_point, hass_data.device_manager, description)
            entities.append(entity)
            res_ids: list[str] = [
                description.door_event_push_res_id,
                # description.low_battery_power_res_id,
                description.lock_event_res_id,
                description.user_id_manual_res_id,
                description.user_id_fingerprint_res_id,
                description.user_id_password_res_id,
                description.user_id_nfc_res_id,
                description.user_id_ble_homekit_res_id,
                description.user_id_temporary_password_res_id,
                description.user_id_manual_with_armed_res_id,
                description.lockout_event_res_id,
                description.door_event_res_id,
                description.open_door_method_id_res_id,
                description.lock_state_res_id,
                description.low_power_battery_res_id,
            ]
            entity_data_update_binding(
                hass, hass_data, entity, aqara_point.did, res_ids
            )

        find_aqara_device_points_and_register(
            hass,
            entry.entry_id,
            hass_data,
            device_ids,
            LOCK_DESCRIPTIONS,
            append_entity,
        )
        async_add_entities(entities)

        # hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, add_lock_power_entity)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, AQARA_DISCOVERY_NEW, async_discover_device)
    )


class AqaraLockEntity(AqaraEntity, LockEntity):
    """Representation of a AqaraLock."""

    entity_description: AqaraLockEntityDescription

    def __init__(  # noqa: C901
        self,
        point: AqaraPoint,
        device_manager: AqaraDeviceManager,
        description: AqaraLockEntityDescription,
    ) -> None:
        """Determine which values to use."""
        super().__init__(point, device_manager)
        self.entity_description = description

        # self.async_on_remove(
        #     async_dispatcher_connect(
        #         self.hass,
        #         f"{AQARA_HA_SIGNAL_UPDATE_ENTITY}_{string_dot_to_underline(self.point.id)}",
        #         self.async_write_ha_state,
        #     )
        # )

    # def point_value_update(self, point: AqaraPoint):
    #     if point.get_res_id() in [
    #         self.entity_description.door_event_push_res_id,
    #         self.entity_description.door_event_res_id,
    #     ]:
    #         # 4: 撬门 5: 门虚掩 1: 门已关 6: 其它 0: 门已开 7: 其它2 2: 超时未关 3: 敲门
    #         if point.get_value() == "1":
    #             self._attr_is_locked = True
    #         if point.get_value() in ["5", "0", "2"]:
    #             self._attr_is_locked = False
    #     if point.get_res_id() == self.entity_description.lock_state_res_id:
    #         # 0: 无 1: 门无法上锁 8: 门虚掩 4: 门已锁 3: 门未上锁 7: 门已锁并反锁 2: 门未关 5: 门已反锁 6: 已开锁
    #         if point.get_value() in ["1", "8", "3", "2"]:
    #             self._attr_is_locked = False
    #         elif point.get_value() in ["4", "7", "5"]:
    #             self._attr_is_locked = True
    #     return None

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked.
        self.entity_description.lock_state_res_id:
           # 0: 无 1: 门无法上锁 8: 门虚掩 4: 门已锁 3: 门未上锁 7: 门已锁并反锁 2: 门未关 5: 门已反锁 6: 已开锁
        """
        if self.entity_description.lock_state_res_id is not None:
            value = self.device_manager.get_point_value(
                self.point.did, self.entity_description.lock_state_res_id
            )
            if value in ["4", "7", "5"]:
                return True
        return False

    @property
    def changed_by(self) -> str | None:

        # @property
        # def changed_by(self) -> int:
        """Last change triggered by."""
        if self.entity_description.open_door_method_id_res_id is not None:
            # 0: 指纹开门 4: 临时密码开门 5: 钥匙开门 3: 蓝牙开门 2: NFC开门 1: 永久密码开门 15: 任意方式室外开门
            open_door_method_id = self.device_manager.get_point_value(
                self.point.did, self.entity_description.open_door_method_id_res_id
            )
            if open_door_method_id == "5":
                return "80030000"
            open_door_method__res_id = {
                "0": self.entity_description.user_id_fingerprint_res_id,
                "1": self.entity_description.user_id_password_res_id,
                "2": self.entity_description.user_id_nfc_res_id,
                "3": self.entity_description.user_id_ble_homekit_res_id,
                "4": self.entity_description.user_id_temporary_password_res_id,
                # "5":""
                # "15"
            }
            res_id = open_door_method__res_id.get(open_door_method_id, "")
            if res_id != "":
                value = self.device_manager.get_point_value(
                    self.point.did,
                    res_id,  # self.entity_description.user_id_fingerprint_res_id
                )
                return value
        return None

    # @property
    # def extra_state_attributes(self) -> dict:
    #     """Return the state attributes."""
    #     attributes = {ATTR_VERIFIED_WRONG_TIMES: self._verified_wrong_times}
    #     return attributes
