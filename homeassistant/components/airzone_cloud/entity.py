"""Entity classes for the Airzone Cloud integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Any

from aioairzone_cloud.const import (
    AZD_AIDOOS,
    AZD_AVAILABLE,
    AZD_FIRMWARE,
    AZD_GROUPS,
    AZD_HOT_WATERS,
    AZD_INSTALLATIONS,
    AZD_NAME,
    AZD_SYSTEM_ID,
    AZD_SYSTEMS,
    AZD_WEBSERVER,
    AZD_WEBSERVERS,
    AZD_ZONES,
)
from aioairzone_cloud.exceptions import AirzoneCloudError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirzoneUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class AirzoneEntity(CoordinatorEntity[AirzoneUpdateCoordinator], ABC):
    """Define an Airzone Cloud entity."""

    _attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Return Airzone Cloud entity availability."""
        return super().available and self.get_airzone_value(AZD_AVAILABLE)

    @abstractmethod
    def get_airzone_value(self, key: str) -> Any:
        """Return Airzone Cloud entity value by key."""

    async def _async_update_params(self, params: dict[str, Any]) -> None:
        """Send Airzone parameters to Cloud API."""
        raise NotImplementedError


class AirzoneAidooEntity(AirzoneEntity):
    """Define an Airzone Cloud Aidoo entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        aidoo_id: str,
        aidoo_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.aidoo_id = aidoo_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, aidoo_id)},
            manufacturer=MANUFACTURER,
            name=aidoo_data[AZD_NAME],
            via_device=(DOMAIN, aidoo_data[AZD_WEBSERVER]),
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return Aidoo value by key."""
        value = None
        if aidoo := self.coordinator.data[AZD_AIDOOS].get(self.aidoo_id):
            value = aidoo.get(key)
        return value

    async def _async_update_params(self, params: dict[str, Any]) -> None:
        """Send Aidoo parameters to Cloud API."""
        _LOGGER.debug("aidoo=%s: update_params=%s", self.entity_id, params)
        try:
            await self.coordinator.airzone.api_set_aidoo_id_params(
                self.aidoo_id, params
            )
        except AirzoneCloudError as error:
            raise HomeAssistantError(
                f"Failed to set {self.entity_id} params: {error}"
            ) from error

        self.coordinator.async_set_updated_data(self.coordinator.airzone.data())


class AirzoneGroupEntity(AirzoneEntity):
    """Define an Airzone Cloud Group entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        group_id: str,
        group_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.group_id = group_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, group_id)},
            manufacturer=MANUFACTURER,
            name=group_data[AZD_NAME],
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return Group value by key."""
        value = None
        if group := self.coordinator.data[AZD_GROUPS].get(self.group_id):
            value = group.get(key)
        return value

    async def _async_update_params(self, params: dict[str, Any]) -> None:
        """Send Group parameters to Cloud API."""
        _LOGGER.debug("group=%s: update_params=%s", self.entity_id, params)
        try:
            await self.coordinator.airzone.api_set_group_id_params(
                self.group_id, params
            )
        except AirzoneCloudError as error:
            raise HomeAssistantError(
                f"Failed to set {self.entity_id} params: {error}"
            ) from error

        self.coordinator.async_set_updated_data(self.coordinator.airzone.data())


class AirzoneHotWaterEntity(AirzoneEntity):
    """Define an Airzone Cloud Hot Water entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        dhw_id: str,
        dhw_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.dhw_id = dhw_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dhw_id)},
            manufacturer=MANUFACTURER,
            name=dhw_data[AZD_NAME],
            via_device=(DOMAIN, dhw_data[AZD_WEBSERVER]),
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return DHW value by key."""
        value = None
        if dhw := self.coordinator.data[AZD_HOT_WATERS].get(self.dhw_id):
            value = dhw.get(key)
        return value

    async def _async_update_params(self, params: dict[str, Any]) -> None:
        """Send DHW parameters to Cloud API."""
        _LOGGER.debug("dhw=%s: update_params=%s", self.entity_id, params)
        try:
            await self.coordinator.airzone.api_set_dhw_id_params(self.dhw_id, params)
        except AirzoneCloudError as error:
            raise HomeAssistantError(
                f"Failed to set {self.entity_id} params: {error}"
            ) from error

        self.coordinator.async_set_updated_data(self.coordinator.airzone.data())


class AirzoneInstallationEntity(AirzoneEntity):
    """Define an Airzone Cloud Installation entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        inst_id: str,
        inst_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.inst_id = inst_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, inst_id)},
            manufacturer=MANUFACTURER,
            name=inst_data[AZD_NAME],
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return Installation value by key."""
        value = None
        if inst := self.coordinator.data[AZD_INSTALLATIONS].get(self.inst_id):
            value = inst.get(key)
        return value

    async def _async_update_params(self, params: dict[str, Any]) -> None:
        """Send Installation parameters to Cloud API."""
        _LOGGER.debug(
            "installation=%s: update_params=%s",
            self.entity_id,
            params,
        )
        try:
            await self.coordinator.airzone.api_set_installation_id_params(
                self.inst_id, params
            )
        except AirzoneCloudError as error:
            raise HomeAssistantError(
                f"Failed to set {self.entity_id} params: {error}"
            ) from error

        self.coordinator.async_set_updated_data(self.coordinator.airzone.data())


class AirzoneSystemEntity(AirzoneEntity):
    """Define an Airzone Cloud System entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        system_id: str,
        system_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.system_id = system_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)},
            manufacturer=MANUFACTURER,
            name=system_data[AZD_NAME],
            via_device=(DOMAIN, system_data[AZD_WEBSERVER]),
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return system value by key."""
        value = None
        if system := self.coordinator.data[AZD_SYSTEMS].get(self.system_id):
            value = system.get(key)
        return value


class AirzoneWebServerEntity(AirzoneEntity):
    """Define an Airzone Cloud WebServer entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        ws_id: str,
        ws_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.ws_id = ws_id

        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, ws_id)},
            identifiers={(DOMAIN, ws_id)},
            manufacturer=MANUFACTURER,
            name=ws_data[AZD_NAME],
            sw_version=ws_data[AZD_FIRMWARE],
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return WebServer value by key."""
        value = None
        if webserver := self.coordinator.data[AZD_WEBSERVERS].get(self.ws_id):
            value = webserver.get(key)
        return value


class AirzoneZoneEntity(AirzoneEntity):
    """Define an Airzone Cloud Zone entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.system_id = zone_data[AZD_SYSTEM_ID]
        self.zone_id = zone_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            manufacturer=MANUFACTURER,
            name=zone_data[AZD_NAME],
            via_device=(DOMAIN, self.system_id),
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return zone value by key."""
        value = None
        if zone := self.coordinator.data[AZD_ZONES].get(self.zone_id):
            value = zone.get(key)
        return value

    async def _async_update_params(self, params: dict[str, Any]) -> None:
        """Send Zone parameters to Cloud API."""
        _LOGGER.debug("zone=%s: update_params=%s", self.entity_id, params)
        try:
            await self.coordinator.airzone.api_set_zone_id_params(self.zone_id, params)
        except AirzoneCloudError as error:
            raise HomeAssistantError(
                f"Failed to set {self.entity_id} params: {error}"
            ) from error

        self.coordinator.async_set_updated_data(self.coordinator.airzone.data())
