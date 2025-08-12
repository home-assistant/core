"""Aqara Home Assistant Base Device Model."""
from __future__ import annotations

from typing import Any

from aqara_iot import AqaraDeviceManager, AqaraPoint

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import HomeAssistantAqaraData
from .const import (
    AQARA_HA_SIGNAL_REGISTER_POINT,
    AQARA_HA_SIGNAL_UPDATE_ENTITY,
    AQARA_HA_SIGNAL_UPDATE_POINT_VALUE,
    DOMAIN,
)


class AqaraEntity(Entity):
    """Aqara base device."""

    _attr_should_poll = False

    def __init__(self, point: AqaraPoint, device_manager: AqaraDeviceManager) -> None:
        """Init AqaraHaEntity."""
        self._attr_unique_id = point.id
        self.point = point
        self._attr_name = point.name
        self.device_manager = device_manager
        device = self.device_manager.get_device(self.point.did)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.point.did)},
            manufacturer="Aqara",
            name=device.device_name,
            model=device.model,
            suggested_area=device.position_name,
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.point.is_online()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{AQARA_HA_SIGNAL_UPDATE_ENTITY}_{self.point.id}",
                self.async_write_ha_state,
            )
        )


def find_aqara_device_points_and_register(
    hass: HomeAssistant,
    hass_data: HomeAssistantAqaraData,
    device_ids: list[str],
    descriptions_map: dict[str, Any],
    append_entity,
):
    """find_aqara_device_points_and_register."""

    for device_id in device_ids:
        device = hass_data.device_manager.device_map[device_id]
        model = device.model
        descriptions = descriptions_map.get(model)

        if descriptions is not None:
            for description in descriptions:
                aqara_point = device.point_map.get(
                    hass_data.device_manager.make_point_id(device.did, description.key)
                )
                aqara_point.name = f"{device.device_name}({description.name})"
                if aqara_point is not None:
                    append_entity(aqara_point, description)
                    async_dispatcher_send(
                        hass,
                        AQARA_HA_SIGNAL_REGISTER_POINT,
                        aqara_point.id,
                    )


def entity_data_update_binding(
    hass: HomeAssistant,
    hass_data: HomeAssistantAqaraData,
    entity: AqaraEntity,
    did: str,
    res_ids: list[str | None],
):
    """Entity_data_update_binding."""

    for res_id in res_ids:
        if res_id is None or res_id == "":
            continue

        point_id = hass_data.device_manager.make_point_id(device_id=did, res_id=res_id)

        entity.async_on_remove(
            async_dispatcher_connect(
                hass,
                f"{AQARA_HA_SIGNAL_UPDATE_ENTITY}_{point_id}",
                entity.async_write_ha_state,
            )
        )
        hass_data.device_listener.async_register_point(point_id)


def entity_point_value_update_binding(
    hass: HomeAssistant,
    hass_data: HomeAssistantAqaraData,
    entity: AqaraEntity,
    did: str,
    res_ids: list[str],
    callback: CALLBACK_TYPE,
):
    """Entity_data_update_binding."""

    for res_id in res_ids:
        if res_id is None or res_id == "":
            continue

        point_id = hass_data.device_manager.make_point_id(device_id=did, res_id=res_id)

        entity.async_on_remove(
            async_dispatcher_connect(
                hass,
                f"{AQARA_HA_SIGNAL_UPDATE_POINT_VALUE}_{point_id}",
                callback,
            )
        )
        hass_data.device_listener.async_register_point(point_id)
