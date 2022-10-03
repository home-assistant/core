"""Update entities for Shelly devices."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final, cast

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlockDeviceWrapper, RpcDeviceWrapper
from .const import BLOCK, CONF_SLEEP_PERIOD, DATA_CONFIG_ENTRY, DOMAIN
from .entity import (
    RestEntityDescription,
    RpcEntityDescription,
    ShellyRestAttributeEntity,
    ShellyRpcAttributeEntity,
    async_setup_entry_rest,
    async_setup_entry_rpc,
)
from .utils import get_device_entry_gen

LOGGER = logging.getLogger(__name__)


@dataclass
class RpcUpdateRequiredKeysMixin:
    """Class for RPC update required keys."""

    latest_version: Callable[[dict], Any]
    install: Callable


@dataclass
class RestUpdateRequiredKeysMixin:
    """Class for REST update required keys."""

    latest_version: Callable[[dict], Any]
    install: Callable


@dataclass
class RpcUpdateDescription(
    RpcEntityDescription, UpdateEntityDescription, RpcUpdateRequiredKeysMixin
):
    """Class to describe a RPC update."""


@dataclass
class RestUpdateDescription(
    RestEntityDescription, UpdateEntityDescription, RestUpdateRequiredKeysMixin
):
    """Class to describe a REST update."""


REST_UPDATES: Final = {
    "fwupdate": RestUpdateDescription(
        name="Firmware Update",
        key="fwupdate",
        latest_version=lambda status: status["update"]["new_version"],
        install=lambda wrapper: wrapper.async_trigger_ota_update(),
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    "fwupdate_beta": RestUpdateDescription(
        name="Beta Firmware Update",
        key="fwupdate",
        latest_version=lambda status: status["update"].get("beta_version"),
        install=lambda wrapper: wrapper.async_trigger_ota_update(beta=True),
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
}

RPC_UPDATES: Final = {
    "fwupdate": RpcUpdateDescription(
        name="Firmware Update",
        key="sys",
        sub_key="available_updates",
        latest_version=lambda status: status.get("stable", {"version": None})[
            "version"
        ],
        install=lambda wrapper: wrapper.async_trigger_ota_update(),
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    "fwupdate_beta": RpcUpdateDescription(
        name="Beta Firmware Update",
        key="sys",
        sub_key="available_updates",
        latest_version=lambda status: status.get("beta", {"version": None})["version"],
        install=lambda wrapper: wrapper.async_trigger_ota_update(beta=True),
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
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

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    entity_description: RestUpdateDescription

    def __init__(
        self,
        wrapper: BlockDeviceWrapper,
        attribute: str,
        description: RestEntityDescription,
    ) -> None:
        """Initialize update entity."""
        super().__init__(wrapper, attribute, description)
        self._in_progress_old_version: str | None = None

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        version = self.wrapper.device.status["update"]["old_version"]
        if version is None:
            return None

        return cast(str, version)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        new_version = self.entity_description.latest_version(
            self.wrapper.device.status,
        )
        if new_version not in (None, ""):
            return cast(str, new_version)

        return self.installed_version

    @property
    def in_progress(self) -> bool:
        """Update installation in progress."""
        return self._in_progress_old_version == self.installed_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        config_entry = self.wrapper.entry
        block_wrapper = self.hass.data[DOMAIN][DATA_CONFIG_ENTRY][
            config_entry.entry_id
        ].get(BLOCK)
        self._in_progress_old_version = self.installed_version
        await self.entity_description.install(block_wrapper)


class RpcUpdateEntity(ShellyRpcAttributeEntity, UpdateEntity):
    """Represent a RPC update entity."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    entity_description: RpcUpdateDescription

    def __init__(
        self,
        wrapper: RpcDeviceWrapper,
        key: str,
        attribute: str,
        description: RpcEntityDescription,
    ) -> None:
        """Initialize update entity."""
        super().__init__(wrapper, key, attribute, description)
        self._in_progress_old_version: str | None = None

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        if self.wrapper.device.shelly is None:
            return None

        return cast(str, self.wrapper.device.shelly["ver"])

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        new_version = self.entity_description.latest_version(
            self.wrapper.device.status[self.key][self.entity_description.sub_key],
        )
        if new_version is not None:
            return cast(str, new_version)

        return self.installed_version

    @property
    def in_progress(self) -> bool:
        """Update installation in progress."""
        return self._in_progress_old_version == self.installed_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        self._in_progress_old_version = self.installed_version
        await self.entity_description.install(self.wrapper)
