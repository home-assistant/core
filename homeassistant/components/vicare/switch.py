"""Viessmann ViCare sensor device."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import datetime
from datetime import timedelta
import logging

from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import ViCareRequiredKeysMixin, ViCareToggleKeysMixin
from .const import DOMAIN, VICARE_API, VICARE_DEVICE_CONFIG, VICARE_NAME

_LOGGER = logging.getLogger(__name__)

SWITCH_DHW_ONETIME_CHARGE = "dhw_onetimecharge"
TIMEDELTA_UPDATE = timedelta(seconds=5)


@dataclass
class ViCareSwitchEntityDescription(
    SwitchEntityDescription, ViCareRequiredKeysMixin, ViCareToggleKeysMixin
):
    """Describes ViCare switch entity."""


SWITCH_DESCRIPTIONS: tuple[ViCareSwitchEntityDescription, ...] = (
    ViCareSwitchEntityDescription(
        key=SWITCH_DHW_ONETIME_CHARGE,
        name="Activate one-time charge",
        icon="mdi:shower-head",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getOneTimeCharge(),
        enabler=lambda api: api.activateOneTimeCharge(),
        disabler=lambda api: api.deactivateOneTimeCharge(),
    ),
)


def _build_entity(name, vicare_api, device_config, description):
    """Create a ViCare button entity."""
    _LOGGER.debug("Found device %s", name)
    try:
        description.value_getter(vicare_api)
        _LOGGER.debug("Found entity %s", name)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("Feature not supported %s", name)
        return None
    except AttributeError:
        _LOGGER.debug("Attribute Error %s", name)
        return None

    return ViCareSwitch(
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
    """Create the ViCare switch devices."""
    name = VICARE_NAME
    api = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]

    entities = []

    for description in SWITCH_DESCRIPTIONS:
        entity = await hass.async_add_executor_job(
            _build_entity,
            f"{name} {description.name}",
            api,
            hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG],
            description,
        )
        if entity is not None:
            entities.append(entity)

    async_add_entities(entities)


class ViCareSwitch(SwitchEntity):
    """Representation of a ViCare switch."""

    entity_description: ViCareSwitchEntityDescription

    def __init__(
        self, name, api, device_config, description: ViCareSwitchEntityDescription
    ):
        """Initialize the switch."""
        self.entity_description = description
        self._device_config = device_config
        self._api = api
        self._ignore_update_until = datetime.datetime.utcnow()
        self._state = None

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    async def async_update(self):
        """update internal state"""
        now = datetime.datetime.utcnow()
        """we have identified that the API does not directly sync the represented state, therefore we want to keep
        an assumed state for a couple of seconds - so lets ignore an update
        """
        if now < self._ignore_update_until:
            _LOGGER.debug(
                "Ignoring Update Request for OneTime Charging for some seconds"
            )
            return

        try:
            with suppress(PyViCareNotSupportedFeatureError):
                _LOGGER.debug("Fetching DHW One Time Charging Status")
                self._state = await self.hass.async_add_executor_job(
                    self.entity_description.value_getter, self._api
                )
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Handle the button press."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                """Turn the switch on."""
                _LOGGER.debug("Enabling DHW One-Time-Charging")
                await self.hass.async_add_executor_job(
                    self.entity_description.enabler, self._api
                )
                self._ignore_update_until = (
                    datetime.datetime.utcnow() + TIMEDELTA_UPDATE
                )
                self._state = True

        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Handle the button press."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                _LOGGER.debug("Disabling DHW One-Time-Charging")
                await self.hass.async_add_executor_job(
                    self.entity_description.disabler, self._api
                )
                self._ignore_update_until = (
                    datetime.datetime.utcnow() + TIMEDELTA_UPDATE
                )
                self._state = False

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
            identifiers={(DOMAIN, self._device_config.getConfig().serial)},
            name=self._device_config.getModel(),
            manufacturer="Viessmann",
            model=self._device_config.getModel(),
            configuration_url="https://developer.viessmann.com/",
        )

    @property
    def unique_id(self) -> str:
        """Return unique ID for this device."""
        tmp_id = (
            f"{self._device_config.getConfig().serial}-{self.entity_description.key}"
        )
        if hasattr(self._api, "id"):
            return f"{tmp_id}-{self._api.id}"
        return tmp_id
