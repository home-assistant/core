"""Entities for the ViCare integration."""

from collections.abc import Generator
from contextlib import contextmanager
import logging
from typing import override

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

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VIESSMANN_DEVELOPER_PORTAL
from .coordinator import ViCareCoordinator

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

        self._gateway_serial = gateway_serial
        self._device_serial = device_serial
        self._device_identifier = identifier
        self._model = model

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device info, resolving the zigbee gateway link at add time."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_identifier)},
            name=self._model,
            manufacturer="Viessmann",
            model=self._model,
            configuration_url=VIESSMANN_DEVELOPER_PORTAL,
        )

        device_serial = self._device_serial
        if device_serial and device_serial.startswith("zigbee-"):
            parts = device_serial.split("-", 2)
            if len(parts) == 3:
                _, zigbee_ieee, _ = parts
                config_entry = self.platform.config_entry
                assert config_entry is not None
                # Link best effort: the gateway may be absent (its main device
                # was omitted or its serial could not be retrieved), in which
                # case the channel stays unlinked rather than aborting setup.
                gateway_device = dr.async_get(self.hass).async_get_device_by_identifier(
                    (DOMAIN, f"{self._gateway_serial}_zigbee_{zigbee_ieee}"),
                    config_entry.entry_id,
                )
                if gateway_device is not None:
                    device_info["via_device_id"] = gateway_device.id
            elif (
                len(parts) == 2
                and len(zigbee_ieee := device_serial.removeprefix("zigbee-")) == 16
            ):
                device_info["serial_number"] = "-".join(
                    zigbee_ieee.upper()[i : i + 2] for i in range(0, 16, 2)
                )
        else:
            device_info["serial_number"] = device_serial

        return device_info


class ViCareCoordinatorEntity(CoordinatorEntity[ViCareCoordinator], ViCareEntity):
    """Base class for ViCare entities backed by the update coordinator."""

    def __init__(
        self,
        coordinator: ViCareCoordinator,
        unique_id_suffix: str,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        component: PyViCareHeatingDeviceComponent | None = None,
    ) -> None:
        """Initialize the entity."""
        CoordinatorEntity.__init__(self, coordinator)
        ViCareEntity.__init__(
            self, unique_id_suffix, device_serial, device_config, device, component
        )
