"""Viessmann ViCare button device."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice, ViCareRequiredKeysMixinWithSet
from .utils import get_device_serial, is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViCareButtonEntityDescription(
    ButtonEntityDescription, ViCareRequiredKeysMixinWithSet
):
    """Describes ViCare button entity."""


BUTTON_DESCRIPTIONS: tuple[ViCareButtonEntityDescription, ...] = (
    ViCareButtonEntityDescription(
        key="activate_onetimecharge",
        translation_key="activate_onetimecharge",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getOneTimeCharge(),
        value_setter=lambda api: api.activateOneTimeCharge(),
    ),
)


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareButton]:
    """Create ViCare button entities for a device."""

    return [
        ViCareButton(
            description,
            get_device_serial(device.api),
            device.config,
            device.api,
        )
        for device in device_list
        for description in BUTTON_DESCRIPTIONS
        if is_supported(description.key, description, device.api)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare button entities."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        )
    )


class ViCareButton(ViCareEntity, ButtonEntity):
    """Representation of a ViCare button."""

    entity_description: ViCareButtonEntityDescription

    def __init__(
        self,
        description: ViCareButtonEntityDescription,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
    ) -> None:
        """Initialize the button."""
        super().__init__(description.key, device_serial, device_config, device)
        self.entity_description = description

    def press(self) -> None:
        """Handle the button press."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self.entity_description.value_setter(self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
