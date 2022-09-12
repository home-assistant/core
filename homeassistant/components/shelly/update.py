"""Update entities for Netgear devices."""
from __future__ import annotations

import logging
from typing import Final, cast, Any, Callable

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
    UpdateEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, KEY_COORDINATOR_FIRMWARE, KEY_ROUTER
from .router import NetgearRouter, NetgearRouterEntity

LOGGER = logging.getLogger(__name__)


@dataclass
class RpcUpdateRequiredKeysMixin:
    """Class for RPC update required keys."""

    installed_version: Callable[[dict, dict], str]
    latest_version: Callable[[dict, dict], str]
    install: Callable

@dataclass
class RestUpdateRequiredKeysMixin:
    """Class for REST update required keys."""

    installed_version: Callable[[dict, dict], str]
    latest_version: Callable[[dict, dict], str]
    install: Callable

@dataclass
class RpcUpdateDescription(RpcEntityDescription, UpdateEntityDescription, RpcUpdateRequiredKeysMixin):
    """Class to describe a RPC update."""

@dataclass
class RestUpdateDescription(RestEntityDescription, UpdateEntityDescription, RestUpdateRequiredKeysMixin):
    """Class to describe a REST update."""


REST_UPDATES: Final = {
    "fwupdate": RestUpdateDescription(
        name="Firmware Update",
        key="fwupdate",
        installed_version=lambda status, shelly: status["update"]["old_version"],
        latest_version=lambda status, shelly: status["update"]["new_version"],
        install=lambda wrapper: wrapper.async_trigger_ota_update(),
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
    ),
    "fwupdate_beta": RestUpdateDescription(
        name="Beta Firmware Update",
        key="fwupdate",
        installed_version=lambda status, shelly: status["update"]["old_version"]
        latest_version=lambda status, shelly: status["update"].get("beta_version", "")
        install=lambda wrapper: wrapper.async_trigger_ota_update(beta=True),
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}

RPC_UPDATES: Final = {
    "fwupdate": RpcUpdateDescription(
        name="Firmware Update",
        key="sys",
        sub_key="available_updates",
        installed_version=lambda status, shelly: shelly["ver"]
        latest_version=lambda status, shelly: status.get("stable", {"version": ""})["version"]
        install=lambda wrapper: wrapper.async_trigger_ota_update(),
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
    ),
    "fwupdate_beta": RpcUpdateDescription(
        name="Beta Firmware Update",
        key="sys",
        sub_key="available_updates",
        installed_version=lambda status, shelly: shelly["ver"]
        latest_version=lambda status, shelly: status.get("beta", {"version": ""})["version"]
        install=lambda wrapper: wrapper.async_trigger_ota_update(beta=True),
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entities for Shelly component."""
    if get_device_entry_gen(config_entry) == 2:
        return async_setup_entry_rpc(
            hass, config_entry, async_add_entities, RPC_UPDATES, RpcUpdateEntity
        )

    if not config_entry.data[CONF_SLEEP_PERIOD]:
        async_setup_entry_rest(
            hass,
            config_entry,
            async_add_entities,
            REST_UPDATES,
            RestUpdateEntity,
        )



class RestUpdateEntity(ShellyRestAttributeEntity, UpdateEntity):
    """Represent a REST update entity."""

    _attr_supported_features = UpdateEntityFeature.INSTALL
    entity_description: RestUpdateDescription

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self.entity_description.installed_version(
            self.wrapper.device.status[self.key][self.entity_description.sub_key],
            self.wrapper.device.shelly,
        )

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.entity_description.latest_version(
            self.wrapper.device.status[self.key][self.entity_description.sub_key],
            self.wrapper.device.shelly,
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        await self.entity_description.install(self.wrapper)


class RpcUpdateEntity(ShellyRpcAttributeEntity, UpdateEntity):
    """Represent a RPC update entity."""

    _attr_supported_features = UpdateEntityFeature.INSTALL
    entity_description: RpcUpdateDescription

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self.entity_description.installed_version(
            self.wrapper.device.status[self.key][self.entity_description.sub_key],
            self.wrapper.device.shelly,
        )

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.entity_description.latest_version(
            self.wrapper.device.status[self.key][self.entity_description.sub_key],
            self.wrapper.device.shelly,
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        await self.entity_description.install(self.wrapper)
