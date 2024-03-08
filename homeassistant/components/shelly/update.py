"""Update entities for Shelly devices."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final, cast

from aioshelly.const import RPC_GENERATIONS
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_SLEEP_PERIOD, OTA_BEGIN, OTA_ERROR, OTA_PROGRESS, OTA_SUCCESS
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
from .utils import get_device_entry_gen, get_release_url

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RpcUpdateRequiredKeysMixin:
    """Class for RPC update required keys."""

    latest_version: Callable[[dict], Any]
    beta: bool


@dataclass(frozen=True)
class RestUpdateRequiredKeysMixin:
    """Class for REST update required keys."""

    latest_version: Callable[[dict], Any]
    beta: bool


@dataclass(frozen=True)
class RpcUpdateDescription(
    RpcEntityDescription, UpdateEntityDescription, RpcUpdateRequiredKeysMixin
):
    """Class to describe a RPC update."""


@dataclass(frozen=True)
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
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
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
        description: RestUpdateDescription,
    ) -> None:
        """Initialize update entity."""
        super().__init__(block_coordinator, attribute, description)
        self._attr_release_url = get_release_url(
            block_coordinator.device.gen,
            block_coordinator.model,
            description.beta,
        )
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
        description: RpcUpdateDescription,
    ) -> None:
        """Initialize update entity."""
        super().__init__(coordinator, key, attribute, description)
        self._ota_in_progress: bool = False
        self._attr_release_url = get_release_url(
            coordinator.device.gen, coordinator.model, description.beta
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_subscribe_ota_events(self._ota_progress_callback)
        )

    @callback
    def _ota_progress_callback(self, event: dict[str, Any]) -> None:
        """Handle device OTA progress."""
        if self._ota_in_progress:
            event_type = event["event"]
            if event_type == OTA_BEGIN:
                self._attr_in_progress = 0
            elif event_type == OTA_PROGRESS:
                self._attr_in_progress = event["progress_percent"]
            elif event_type in (OTA_ERROR, OTA_SUCCESS):
                self._attr_in_progress = False
                self._ota_in_progress = False
            self.async_write_ha_state()

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

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
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
            self._ota_in_progress = True
            LOGGER.debug("OTA update call successful")


class RpcSleepingUpdateEntity(
    ShellySleepingRpcAttributeEntity, UpdateEntity, RestoreEntity
):
    """Represent a RPC sleeping update entity."""

    entity_description: RpcUpdateDescription

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.last_state = await self.async_get_last_state()

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

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes."""
        if not self.coordinator.device.initialized:
            return None

        return get_release_url(
            self.coordinator.device.gen,
            self.coordinator.model,
            self.entity_description.beta,
        )
