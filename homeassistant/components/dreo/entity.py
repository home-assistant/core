"""Dreo for device."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from hscloud.hscloudexception import HsCloudException, HsCloudBusinessException, HsCloudAccessDeniedException, HsCloudFlowControlException

import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DreoEntity(Entity):
    """Representation of a base a coordinated Dreo Entity."""

    def __init__(self, device, config_entry):
        """Initialize the coordinated Dreo Device."""
        self._name = device.get("deviceName")
        self._device = device
        self._config_entry = config_entry
        self._model = device.get("model")
        self._device_id = device.get("deviceSn")
        self._unique_id = device.get("deviceSn")
        self._mcuFirmwareVersion = device.get("mcuFirmwareVersion")
        self._moduleFirmwareVersion = device.get("moduleFirmwareVersion")
        self._attr_unique_id = self._unique_id
        self._attr_name = self._name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Dreo",
            model=self._model,
            name=self._name,
            sw_version=self._moduleFirmwareVersion,
            hw_version=self._mcuFirmwareVersion
        )

    def _try_command(self, mask_error, **kwargs):
        """Call a hscluod device command handling error messages."""
        _LOGGER.info("command: {}".format(kwargs))
        try:
            self._config_entry.runtime_data.client.update_status(self._device_id, **kwargs)
            return True

        except HsCloudException as exc:
            _LOGGER.error(mask_error)
            return False

        except HsCloudBusinessException as exc:
            _LOGGER.error(mask_error)
            return False

        except HsCloudAccessDeniedException as exc:
            _LOGGER.error(mask_error)
            return False

        except HsCloudFlowControlException as exc:
            _LOGGER.error(mask_error)
            return False

        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(mask_error)
            return False