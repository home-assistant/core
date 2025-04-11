"""Dreo for device."""

import logging
from typing import Any

from hscloud.hscloudexception import (
    HsCloudAccessDeniedException,
    HsCloudBusinessException,
    HsCloudException,
    HsCloudFlowControlException,
)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import DreoConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DreoEntity(Entity):
    """Representation of a base Dreo Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: dict[str, Any],
        config_entry: DreoConfigEntry,
        unique_id_suffix: str | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize the Dreo entity.

        Args:
            device: Device information dictionary
            config_entry: The config entry
            unique_id_suffix: Optional suffix for unique_id to differentiate multiple entities from same device
            name: Optional entity name, None will use the device name as-is

        """
        super().__init__()
        self._config_entry = config_entry
        self._model = device.get("model")
        self._device_id = device.get("deviceSn")
        self._attr_name = name

        if unique_id_suffix:
            self._attr_unique_id = f"{self._device_id}_{unique_id_suffix}"
        else:
            self._attr_unique_id = self._device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer="Dreo",
            model=self._model,
            name=device.get("deviceName"),
            sw_version=device.get("moduleFirmwareVersion"),
            hw_version=device.get("mcuFirmwareVersion"),
        )

    def _send_command(self, translation_key: str, **kwargs) -> None:
        """Call a hscloud device command and handle errors."""

        try:
            self._config_entry.runtime_data.client.update_status(
                self._device_id, **kwargs
            )

        except HsCloudException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=translation_key
            ) from ex

        except HsCloudBusinessException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=translation_key
            ) from ex

        except HsCloudAccessDeniedException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=translation_key
            ) from ex

        except HsCloudFlowControlException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=translation_key
            ) from ex
