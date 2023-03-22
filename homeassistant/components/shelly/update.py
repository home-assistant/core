"""Update entities for Shelly devices."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final, cast

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SLEEP_PERIOD
from .coordinator import ShellyBlockCoordinator, ShellyRpcCoordinator
from .entity import (
    RestEntityDescription,
    RpcEntityDescription,
    ShellyRestAttributeEntity,
    ShellyRpcAttributeEntity,
    ShellySleepingRpcAttributeEntity,
    async_setup_entry_rest,
    async_setup_entry_rpc,
)
from .utils import get_device_entry_gen

LOGGER = logging.getLogger(__name__)


@dataclass
class RpcUpdateRequiredKeysMixin:
    """Class for RPC update required keys."""

    latest_version: Callable[[dict], Any]
    beta: bool


@dataclass
class RestUpdateRequiredKeysMixin:
    """Class for REST update required keys."""

    latest_version: Callable[[dict], Any]
    beta: bool


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
        name="Firmware update",
        key="fwupdate",
        latest_version=lambda status: status["update"]["new_version"],
        beta=False,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    "fwupdate_beta": RestUpdateDescription(
        name="Beta firmware update",
        key="fwupdate",
        latest_version=lambda status: status["update"].get("beta_version"),
        beta=True,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
}

RPC_UPDATES: Final = {
    "fwupdate": RpcUpdateDescription(
        name="Firmware update",
        key="sys",
        sub_key="available_updates",
        latest_version=lambda status: status.get("stable", {"version": ""})["version"],
        beta=False,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
    ),
    "fwupdate_beta": RpcUpdateDescription(
        name="Beta firmware update",
        key="sys",
        sub_key="available_updates",
        latest_version=lambda status: status.get("beta", {"version": ""})["version"],
        beta=True,
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
        if config_entry.data[CONF_SLEEP_PERIOD]:
            async_setup_entry_rpc(
                hass,
                config_entry,
                async_add_entities,
                RPC_UPDATES,
                RpcSleepingUpdateEntity,
            )
        else:
            async_setup_entry_rpc(
                hass, config_entry, async_add_entities, RPC_UPDATES, RpcUpdateEntity
            )
        return

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
        block_coordinator: ShellyBlockCoordinator,
        attribute: str,
        description: RestEntityDescription,
    ) -> None:
        """Initialize update entity."""
        super().__init__(block_coordinator, attribute, description)
        self._in_progress_old_version: str | None = None

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return cast(str, self.block_coordinator.device.status["update"]["old_version"])

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        new_version = self.entity_description.latest_version(
            self.block_coordinator.device.status,
        )
        if new_version:
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
        beta = self.entity_description.beta
        update_data = self.coordinator.device.status["update"]
        LOGGER.debug("OTA update service - update_data: %s", update_data)

        new_version = update_data["new_version"]
        if beta:
            new_version = update_data["beta_version"]

        LOGGER.info(
            "Starting OTA update of device %s from '%s' to '%s'",
            self.name,
            self.coordinator.device.firmware_version,
            new_version,
        )
        try:
            result = await self.coordinator.device.trigger_ota_update(beta=beta)
        except DeviceConnectionError as err:
            raise HomeAssistantError(f"Error starting OTA update: {repr(err)}") from err
        except InvalidAuthError:
            self.coordinator.entry.async_start_reauth(self.hass)
        else:
            LOGGER.debug("Result of OTA update call: %s", result)


class RpcUpdateEntity(ShellyRpcAttributeEntity, UpdateEntity):
    """Represent a RPC update entity."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    entity_description: RpcUpdateDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcEntityDescription,
    ) -> None:
        """Initialize update entity."""
        super().__init__(coordinator, key, attribute, description)
        self._in_progress_old_version: str | None = None

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return cast(str, self.coordinator.device.shelly["ver"])

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        new_version = self.entity_description.latest_version(self.sub_status)
        if new_version:
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
        beta = self.entity_description.beta
        update_data = self.coordinator.device.status["sys"]["available_updates"]
        LOGGER.debug("OTA update service - update_data: %s", update_data)

        new_version = update_data.get("stable", {"version": ""})["version"]
        if beta:
            new_version = update_data.get("beta", {"version": ""})["version"]

        LOGGER.info(
            "Starting OTA update of device %s from '%s' to '%s'",
            self.coordinator.name,
            self.coordinator.device.firmware_version,
            new_version,
        )
        try:
            await self.coordinator.device.trigger_ota_update(beta=beta)
        except DeviceConnectionError as err:
            raise HomeAssistantError(
                f"OTA update connection error: {repr(err)}"
            ) from err
        except RpcCallError as err:
            raise HomeAssistantError(f"OTA update request error: {repr(err)}") from err
        except InvalidAuthError:
            self.coordinator.entry.async_start_reauth(self.hass)
        else:
            LOGGER.debug("OTA update call successful")


class RpcSleepingUpdateEntity(ShellySleepingRpcAttributeEntity, UpdateEntity):
    """Represent a RPC sleeping update entity."""

    entity_description: RpcUpdateDescription

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        if self.coordinator.device.initialized:
            return cast(str, self.coordinator.device.shelly["ver"])

        if self.last_state is None:
            return None

        return self.last_state.attributes.get(ATTR_INSTALLED_VERSION)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if self.coordinator.device.initialized:
            new_version = self.entity_description.latest_version(self.sub_status)
            if new_version:
                return cast(str, new_version)

            return self.installed_version

        if self.last_state is None:
            return None

        return self.last_state.attributes.get(ATTR_LATEST_VERSION)
