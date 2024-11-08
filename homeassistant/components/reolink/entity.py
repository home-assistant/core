"""Reolink parent entity class."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from reolink_aio.api import DUAL_LENS_MODELS, Chime, Host

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import ReolinkData
from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class ReolinkEntityDescription(EntityDescription):
    """A class that describes entities for Reolink."""

    cmd_key: str | None = None
    cmd_id: int | None = None


@dataclass(frozen=True, kw_only=True)
class ReolinkChannelEntityDescription(ReolinkEntityDescription):
    """A class that describes entities for a camera channel."""

    supported: Callable[[Host, int], bool] = lambda api, ch: True


@dataclass(frozen=True, kw_only=True)
class ReolinkHostEntityDescription(ReolinkEntityDescription):
    """A class that describes host entities."""

    supported: Callable[[Host], bool] = lambda api: True


@dataclass(frozen=True, kw_only=True)
class ReolinkChimeEntityDescription(ReolinkEntityDescription):
    """A class that describes entities for a chime."""

    supported: Callable[[Chime], bool] = lambda chime: True


class ReolinkHostCoordinatorEntity(CoordinatorEntity[DataUpdateCoordinator[None]]):
    """Parent class for entities that control the Reolink NVR itself, without a channel.

    A camera connected directly to HomeAssistant without using a NVR is in the reolink API
    basically a NVR with a single channel that has the camera connected to that channel.
    """

    _attr_has_entity_name = True
    entity_description: ReolinkEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        coordinator: DataUpdateCoordinator[None] | None = None,
    ) -> None:
        """Initialize ReolinkHostCoordinatorEntity."""
        if coordinator is None:
            coordinator = reolink_data.device_coordinator
        super().__init__(coordinator)

        self._host = reolink_data.host
        self._attr_unique_id = f"{self._host.unique_id}_{self.entity_description.key}"

        http_s = "https" if self._host.api.use_https else "http"
        self._conf_url = f"{http_s}://{self._host.api.host}:{self._host.api.port}"
        self._dev_id = self._host.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._dev_id)},
            connections={(CONNECTION_NETWORK_MAC, self._host.api.mac_address)},
            name=self._host.api.nvr_name,
            model=self._host.api.model,
            model_id=self._host.api.item_number,
            manufacturer=self._host.api.manufacturer,
            hw_version=self._host.api.hardware_version,
            sw_version=self._host.api.sw_version,
            serial_number=self._host.api.uid,
            configuration_url=self._conf_url,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._host.api.session_active and super().available

    @callback
    def _push_callback(self) -> None:
        """Handle incoming TCP push event."""
        self.async_write_ha_state()

    def register_callback(self, unique_id: str, cmd_id: int) -> None:
        """Register callback for TCP push events."""
        self._host.api.baichuan.register_callback(  # pragma: no cover
            unique_id, self._push_callback, cmd_id
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        cmd_key = self.entity_description.cmd_key
        cmd_id = self.entity_description.cmd_id
        if cmd_key is not None:
            self._host.async_register_update_cmd(cmd_key)
        if cmd_id is not None and self._attr_unique_id is not None:
            self.register_callback(self._attr_unique_id, cmd_id)

    async def async_will_remove_from_hass(self) -> None:
        """Entity removed."""
        cmd_key = self.entity_description.cmd_key
        cmd_id = self.entity_description.cmd_id
        if cmd_key is not None:
            self._host.async_unregister_update_cmd(cmd_key)
        if cmd_id is not None and self._attr_unique_id is not None:
            self._host.api.baichuan.unregister_callback(self._attr_unique_id)

        await super().async_will_remove_from_hass()

    async def async_update(self) -> None:
        """Force full update from the generic entity update service."""
        self._host.last_wake = 0
        await super().async_update()


class ReolinkChannelCoordinatorEntity(ReolinkHostCoordinatorEntity):
    """Parent class for Reolink hardware camera entities connected to a channel of the NVR."""

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        coordinator: DataUpdateCoordinator[None] | None = None,
    ) -> None:
        """Initialize ReolinkChannelCoordinatorEntity for a hardware camera connected to a channel of the NVR."""
        super().__init__(reolink_data, coordinator)

        self._channel = channel
        if self._host.api.supported(channel, "UID"):
            self._attr_unique_id = f"{self._host.unique_id}_{self._host.api.camera_uid(channel)}_{self.entity_description.key}"
        else:
            self._attr_unique_id = (
                f"{self._host.unique_id}_{channel}_{self.entity_description.key}"
            )

        dev_ch = channel
        if self._host.api.model in DUAL_LENS_MODELS:
            dev_ch = 0

        if self._host.api.is_nvr:
            if self._host.api.supported(dev_ch, "UID"):
                self._dev_id = (
                    f"{self._host.unique_id}_{self._host.api.camera_uid(dev_ch)}"
                )
            else:
                self._dev_id = f"{self._host.unique_id}_ch{dev_ch}"

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._dev_id)},
                via_device=(DOMAIN, self._host.unique_id),
                name=self._host.api.camera_name(dev_ch),
                model=self._host.api.camera_model(dev_ch),
                manufacturer=self._host.api.manufacturer,
                hw_version=self._host.api.camera_hardware_version(dev_ch),
                sw_version=self._host.api.camera_sw_version(dev_ch),
                serial_number=self._host.api.camera_uid(dev_ch),
                configuration_url=self._conf_url,
            )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._host.api.camera_online(self._channel)

    def register_callback(self, unique_id: str, cmd_id) -> None:
        """Register callback for TCP push events."""
        self._host.api.baichuan.register_callback(
            unique_id, self._push_callback, cmd_id, self._channel
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        cmd_key = self.entity_description.cmd_key
        if cmd_key is not None:
            self._host.async_register_update_cmd(cmd_key, self._channel)

    async def async_will_remove_from_hass(self) -> None:
        """Entity removed."""
        cmd_key = self.entity_description.cmd_key
        if cmd_key is not None:
            self._host.async_unregister_update_cmd(cmd_key, self._channel)

        await super().async_will_remove_from_hass()


class ReolinkChimeCoordinatorEntity(ReolinkChannelCoordinatorEntity):
    """Parent class for Reolink chime entities connected."""

    def __init__(
        self,
        reolink_data: ReolinkData,
        chime: Chime,
        coordinator: DataUpdateCoordinator[None] | None = None,
    ) -> None:
        """Initialize ReolinkChimeCoordinatorEntity for a chime."""
        super().__init__(reolink_data, chime.channel, coordinator)

        self._chime = chime

        self._attr_unique_id = (
            f"{self._host.unique_id}_chime{chime.dev_id}_{self.entity_description.key}"
        )
        cam_dev_id = self._dev_id
        self._dev_id = f"{self._host.unique_id}_chime{chime.dev_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._dev_id)},
            via_device=(DOMAIN, cam_dev_id),
            name=chime.name,
            model="Reolink Chime",
            manufacturer=self._host.api.manufacturer,
            serial_number=str(chime.dev_id),
            configuration_url=self._conf_url,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._chime.online and super().available
