"""Viessmann ViCare button device."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareUtils import (
    PyViCareInternalServerError,
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ViCareRequiredKeysMixinWithSet
from .const import DOMAIN, VICARE_DEVICE_CONFIG, VICARE_NAME
from .helpers import get_device_name, get_unique_device_id, get_unique_id

_LOGGER = logging.getLogger(__name__)

BUTTON_DHW_ACTIVATE_ONETIME_CHARGE = "activate_onetimecharge"


@dataclass
class ViCareButtonEntityDescription(
    ButtonEntityDescription, ViCareRequiredKeysMixinWithSet
):
    """Describes ViCare button entity."""


BUTTON_DESCRIPTIONS: tuple[ViCareButtonEntityDescription, ...] = (
    ViCareButtonEntityDescription(
        key=BUTTON_DHW_ACTIVATE_ONETIME_CHARGE,
        name="Activate one-time charge",
        icon="mdi:shower-head",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getOneTimeCharge(),
        value_setter=lambda api: api.activateOneTimeCharge(),
    ),
)


def _build_entity(name, vicare_api, device_config, description):
    """Create a ViCare button entity."""
    _LOGGER.debug("Found device %s", name)
    try:
        description.value_getter(vicare_api)
        _LOGGER.debug("Found entity %s", name)
    except PyViCareInternalServerError as server_error:
        _LOGGER.info(
            "Server error ( %s): Not creating entity %s", server_error.message, name
        )
        return None
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("Feature not supported %s", name)
        return None
    except AttributeError:
        _LOGGER.debug("Attribute Error %s", name)
        return None

    return ViCareButton(
        name,
        vicare_api,
        device_config,
        description,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare button entities."""
    entities = await hass.async_add_executor_job(
        create_all_entities, hass, config_entry
    )
    async_add_entities(entities)


def create_all_entities(hass: HomeAssistant, config_entry: ConfigEntry):
    """Create entities for all devices and their circuits, burners or compressors if applicable."""
    name = VICARE_NAME
    entities = []

    for device in hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG]:
        api = device.asAutoDetectDevice()

        for description in BUTTON_DESCRIPTIONS:
            entity = _build_entity(
                f"{name} {description.name}",
                api,
                device,
                description,
            )
            if entity is not None:
                entities.append(entity)

    return entities


class ViCareButton(ButtonEntity):
    """Representation of a ViCare button."""

    entity_description: ViCareButtonEntityDescription

    def __init__(
        self, name, api, device_config, description: ViCareButtonEntityDescription
    ) -> None:
        """Initialize the button."""
        self.entity_description = description
        self._device_config = device_config
        self._api = api

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

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    get_unique_device_id(self._device_config),
                )
            },
            name=get_device_name(self._device_config),
            manufacturer="Viessmann",
            model=self._device_config.getModel(),
            configuration_url="https://developer.viessmann.com/",
        )

    @property
    def unique_id(self) -> str:
        """Return unique ID for this device."""
        return get_unique_id(
            self._api, self._device_config, self.entity_description.key
        )
