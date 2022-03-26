"""Support for Synology DSM update platform."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.components.update.const import UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlockDeviceWrapper, RpcDeviceWrapper
from .const import BLOCK, DATA_CONFIG_ENTRY, DOMAIN
from .entity import (
    RestEntityDescription,
    RpcEntityDescription,
    ShellyRestAttributeEntity,
    ShellyRpcAttributeEntity,
    async_setup_entry_rest,
    async_setup_entry_rpc,
)
from .utils import get_device_entry_gen


@dataclass
class RestUpdateEntityDescription(RestEntityDescription, UpdateEntityDescription):
    """Class to describe a REST update entity."""

    current_version: Callable[[dict], str | None] | None = None
    latest_version: Callable[[dict], str | None] | None = None
    release_url: str | None = None
    install_callback: Callable[
        [BlockDeviceWrapper], Coroutine[Any, Any, None]
    ] | None = None


@dataclass
class RpcUpdateEntityDescription(RpcEntityDescription, UpdateEntityDescription):
    """Class to describe a RPC update entity."""

    current_version: Callable[[dict], str | None] | None = None
    latest_version: Callable[[dict[str, dict]], str | None] | None = None
    release_url: str | None = None
    install_callback: Callable[
        [RpcDeviceWrapper], Coroutine[Any, Any, None]
    ] | None = None


BLOCK_UPDATE_ENTITIES: Final = {
    "fwupdate": RestUpdateEntityDescription(
        key="fwupdate",
        name="Firmware Update",
        device_class=UpdateDeviceClass.FIRMWARE,
        current_version=lambda update: update.get("old_version"),
        latest_version=lambda update: update.get("new_version"),
        release_url="https://shelly-api-docs.shelly.cloud/gen1/#changelog",
        install_callback=lambda wrapper: wrapper.async_trigger_ota_update(),
        entity_category=EntityCategory.CONFIG,
    ),
    "fwupdate_beta": RestUpdateEntityDescription(
        key="fwupdate_beta",
        name="Firmware Update Beta",
        entity_registry_enabled_default=False,
        device_class=UpdateDeviceClass.FIRMWARE,
        current_version=lambda update: update.get("old_version"),
        latest_version=lambda update: update.get("beta_version"),
        install_callback=lambda wrapper: wrapper.async_trigger_ota_update(beta=True),
        entity_category=EntityCategory.CONFIG,
    ),
}

RPC_UPDATE_ENTITY: Final = {
    "fwupdate": RpcUpdateEntityDescription(
        key="sys",
        sub_key="available_updates",
        name="Firmware Update",
        device_class=UpdateDeviceClass.FIRMWARE,
        current_version=lambda shelly: shelly.get("ver"),
        latest_version=lambda status: status.get("stable", {"version": None}).get(
            "version"
        ),
        release_url="https://shelly-api-docs.shelly.cloud/gen2/changelog",
        install_callback=lambda wrapper: wrapper.async_trigger_ota_update(),
        entity_category=EntityCategory.CONFIG,
    ),
    "fwupdate_beta": RpcUpdateEntityDescription(
        key="sys",
        sub_key="available_updates",
        name="Firmware Update Beta",
        entity_registry_enabled_default=False,
        device_class=UpdateDeviceClass.FIRMWARE,
        current_version=lambda shelly: shelly.get("ver"),
        latest_version=lambda status: status.get("beta", {"version": None}).get(
            "version"
        ),
        install_callback=lambda wrapper: wrapper.async_trigger_ota_update(beta=True),
        entity_category=EntityCategory.CONFIG,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up shelly update entity."""
    if get_device_entry_gen(config_entry) == 2:
        await async_setup_entry_rpc(
            hass, config_entry, async_add_entities, RPC_UPDATE_ENTITY, RpcUpdateEntitry
        )
    else:
        await async_setup_entry_rest(
            hass,
            config_entry,
            async_add_entities,
            BLOCK_UPDATE_ENTITIES,
            RestUpdateEntity,
        )


class RestUpdateEntity(ShellyRestAttributeEntity, UpdateEntity):
    """Represent a REST update entity."""

    entity_description: RestUpdateEntityDescription
    _attr_supported_features = UpdateEntityFeature.INSTALL

    @property
    def current_version(self) -> str | None:
        """Version currently in use."""
        if (
            self.entity_description.current_version is None
            or (update := self.wrapper.device.status.get("update")) is None
        ):
            return None

        return self.entity_description.current_version(update)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if (
            self.entity_description.latest_version is None
            or (update := self.wrapper.device.status.get("update")) is None
        ):
            return None

        if (result := self.entity_description.latest_version(update)) is not None:
            return result

        return self.current_version

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return self.entity_description.release_url

    async def async_install(
        self,
        version: str | None = None,
        backup: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Triggers the Shelly button press service."""
        assert self.registry_entry
        assert self.registry_entry.config_entry_id
        block_wrapper: BlockDeviceWrapper = self.hass.data[DOMAIN][DATA_CONFIG_ENTRY][
            self.registry_entry.config_entry_id
        ][BLOCK]
        if self.entity_description.install_callback is not None:
            await self.entity_description.install_callback(block_wrapper)


class RpcUpdateEntitry(ShellyRpcAttributeEntity, UpdateEntity):
    """Represent a RPC update entity."""

    entity_description: RpcUpdateEntityDescription
    _attr_supported_features = UpdateEntityFeature.INSTALL

    @property
    def current_version(self) -> str | None:
        """Version currently in use."""
        if (
            self.entity_description.current_version is None
            or self.wrapper.device.shelly is None
        ):
            return None

        return self.entity_description.current_version(
            self.wrapper.device.shelly,
        )

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if (
            self.entity_description.latest_version is None
            or (
                status := self.wrapper.device.status.get(self.key, {}).get(
                    self.entity_description.sub_key
                )
            )
            is None
        ):
            return None

        return self.entity_description.latest_version(status)

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return self.entity_description.release_url

    async def async_install(
        self,
        version: str | None = None,
        backup: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Triggers the Shelly button press service."""
        if self.entity_description.install_callback is not None:
            await self.entity_description.install_callback(self.wrapper)
