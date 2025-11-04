"""Viessmann ViCare switch device."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import datetime
import logging
from typing import Any

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice, ViCareRequiredKeysMixinWithSwitch
from .utils import get_device_serial, is_supported

_LOGGER = logging.getLogger(__name__)

SWITCH_DHW_ONETIME_CHARGE = "dhw_onetimecharge"
TIMEDELTA_UPDATE = datetime.timedelta(seconds=5)


@dataclass(frozen=True)
class ViCareSwitchEntityDescription(
    SwitchEntityDescription, ViCareRequiredKeysMixinWithSwitch
):
    """Describes ViCare switch entity."""


VENTILATION_SWITCH_DESCRIPTIONS: tuple[ViCareSwitchEntityDescription, ...] = (
    ViCareSwitchEntityDescription(
        key="ventilation_quickmode_boost",
        translation_key="ventilation_quickmode_boost",
        value_getter=lambda api: api.getVentilationQuickmode("forcedLevelFour"),
        enabler=lambda api: api.activateVentilationQuickmode("forcedLevelFour"),
        disabler=lambda api: api.deactivateVentilationQuickmode("forcedLevelFour"),
    ),
    ViCareSwitchEntityDescription(
        key="ventilation_quickmode_silence",
        translation_key="ventilation_quickmode_silence",
        value_getter=lambda api: api.getVentilationQuickmode("silent"),
        enabler=lambda api: api.activateVentilationQuickmode("silent"),
        disabler=lambda api: api.deactivateVentilationQuickmode("silent"),
    ),
)


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareSwitch]:
    """Create ViCare switch entities for a device."""

    return [
        ViCareSwitch(
            description,
            get_device_serial(device.api),
            device.config,
            device.api,
        )
        for device in device_list
        for description in VENTILATION_SWITCH_DESCRIPTIONS
        if device.api.isVentilationDevice()
        and is_supported(description.key, description.value_getter, device.api)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the ViCare switch entities."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        )
    )


class ViCareSwitch(ViCareEntity, SwitchEntity):
    """Representation of a ViCare switch."""

    entity_description: ViCareSwitchEntityDescription

    def __init__(
        self,
        description: ViCareSwitchEntityDescription,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
    ) -> None:
        """Initialize the button."""
        super().__init__(description.key, device_serial, device_config, device)
        self.entity_description = description

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Handle the switch turn on."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                await self.hass.async_add_executor_job(
                    self.entity_description.enabler, self._api
                )
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Handle the switch turn off."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                await self.hass.async_add_executor_job(
                    self.entity_description.disabler, self._api
                )
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    def update(self) -> None:
        """Update internal state."""

        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_is_on = bool(self.entity_description.value_getter(self._api))
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
