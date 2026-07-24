"""Entities for the ViCare integration."""

from collections.abc import Generator
from contextlib import contextmanager
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
)
from PyViCare.PyViCareUtils import (
    PyViCareDeviceCommunicationError,
    PyViCareInternalServerError,
    PyViCareInvalidDataError,
    PyViCareRateLimitError,
)
from requests.exceptions import ConnectionError as RequestConnectionError

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, VIESSMANN_DEVELOPER_PORTAL

_LOGGER = logging.getLogger(__name__)


class ViCareEntity(Entity):
    """Base class for ViCare entities."""

    _attr_has_entity_name = True

    @contextmanager
    def vicare_api_handler(self) -> Generator[None]:
        """Handle common ViCare API errors."""
        try:
            yield
        except RequestConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as err:
            _LOGGER.error("ViCare API rate limit exceeded: %s", err)
        except PyViCareInvalidDataError as err:
            _LOGGER.error("Invalid data from ViCare server: %s", err)
        except PyViCareDeviceCommunicationError as err:
            _LOGGER.warning("Device communication error: %s", err)
        except PyViCareInternalServerError as err:
            _LOGGER.warning("ViCare server error: %s", err)

    def __init__(
        self,
        unique_id_suffix: str,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        component: PyViCareHeatingDeviceComponent | None = None,
    ) -> None:
        """Initialize the entity."""
        gateway_serial = device_config.getConfig().serial
        device_id = device_config.getId()
        model = device_config.getModel().replace("_", " ")

        identifier = (
            f"{gateway_serial}_{device_serial.replace('-', '_')}"
            if device_serial is not None
            else f"{gateway_serial}_{device_id}"
        )

        self._api: PyViCareDevice | PyViCareHeatingDeviceComponent = component or device
        self._attr_unique_id = f"{identifier}-{unique_id_suffix}"
        if component:
            self._attr_unique_id += f"-{component.id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=model,
            manufacturer="Viessmann",
            model=model,
            configuration_url=VIESSMANN_DEVELOPER_PORTAL,
        )

        if device_serial and device_serial.startswith("zigbee-"):
            parts = device_serial.split("-", 2)
            if len(parts) == 3:
                _, zigbee_ieee, _ = parts
                self._attr_device_info["via_device"] = (
                    DOMAIN,
                    f"{gateway_serial}_zigbee_{zigbee_ieee}",
                )
            elif (
                len(parts) == 2
                and len(zigbee_ieee := device_serial.removeprefix("zigbee-")) == 16
            ):
                self._attr_device_info["serial_number"] = "-".join(
                    zigbee_ieee.upper()[i : i + 2] for i in range(0, 16, 2)
                )
        else:
            self._attr_device_info["serial_number"] = device_serial
