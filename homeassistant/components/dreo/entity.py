"""Dreo for device."""

import logging

from hscloud.hscloudexception import (
    HsCloudAccessDeniedException,
    HsCloudBusinessException,
    HsCloudException,
    HsCloudFlowControlException,
)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DreoEntity(Entity):
    """Representation of a base a coordinated Dreo Entity."""

    def __init__(self, device, config_entry):
        """Initialize the coordinated Dreo Device."""
        self._config_entry = config_entry
        self._model = device.get("model")
        self._device_id = device.get("deviceSn")
        self._attr_unique_id = device.get("deviceSn")
        self._attr_name = device.get("deviceName")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Dreo",
            model=self._model,
            name=self._attr_name,
            sw_version=device.get("moduleFirmwareVersion"),
            hw_version=device.get("mcuFirmwareVersion"),
        )

    def _try_command(self, mask_error, **kwargs) -> bool:
        """Call a hscluod device command handling error messages."""
        _LOGGER.info(f"command: {kwargs}")
        try:
            self._config_entry.runtime_data.client.update_status(
                self._device_id, **kwargs
            )
            return True

        except HsCloudException as ex:
            _LOGGER.error(mask_error)
            raise HomeAssistantError(mask_error) from ex

        except HsCloudBusinessException as ex:
            _LOGGER.error(mask_error)
            raise HomeAssistantError(mask_error) from ex

        except HsCloudAccessDeniedException as ex:
            _LOGGER.error(mask_error)
            raise HomeAssistantError(mask_error) from ex

        except HsCloudFlowControlException as ex:
            _LOGGER.error(mask_error)
            raise HomeAssistantError(mask_error) from ex

        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(mask_error)
            raise HomeAssistantError(mask_error) from ex
