from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from hscloud.hscloudexception import HsCloudException, HsCloudAccessDeniedException, HsCloudFlowControlException

import logging
from .const import DOMAIN, MANAGER

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class DreoEntity(Entity):
    """Representation of a base a coordinated Dreo Entity."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the coordinated Dreo Device."""
        self._name = name
        self._device = device
        self._config_entry = entry
        self._model = device.get("model")
        self._device_id = device.get("deviceSn")
        self._unique_id = unique_id
        self._mcuFirmwareVersion = device.get("mcuFirmwareVersion")
        self._moduleFirmwareVersion = device.get("moduleFirmwareVersion")

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Dreo",
            model=self._model,
            name=self._name,
            sw_version=self._moduleFirmwareVersion,
            hw_version=self._mcuFirmwareVersion
        )
        return device_info

    def _try_command(self, mask_error, **kwargs):
        """Call a hscluod device command handling error messages."""
        _LOGGER.info(f"command: {kwargs}")
        try:
            manager = self.hass.data[DOMAIN][self._config_entry.entry_id].get(MANAGER)
            manager.update_status(self._device_id, **kwargs)
            return True

        except HsCloudException as exc:
            _LOGGER.error(mask_error)
            raise ValueError(
                f"{exc}"
            )

        except HsCloudAccessDeniedException as exc:
            _LOGGER.error(mask_error)
            raise ValueError(
                f"{exc}"
            )

        except HsCloudFlowControlException as exc:
            _LOGGER.error(mask_error)
            raise ValueError(
                f"{exc}"
            )