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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .circulation import DhwCirculationBoostState, async_activate_dhw_circulation_boost
from .const import (
    CONF_HEAT_TIMEOUT_MINUTES,
    CONF_MIN_BOOST_TEMPERATURE,
    CONF_WARM_WATER_DELAY_MINUTES,
    DEFAULT_DHW_BOOST_HEAT_TIMEOUT_MINUTES,
    DEFAULT_DHW_BOOST_MIN_TEMPERATURE,
    DEFAULT_DHW_BOOST_WARM_WATER_DELAY_MINUTES,
    DOMAIN,
)
from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice, ViCareRequiredKeysMixinWithSet
from .utils import get_device_serial, is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViCareButtonEntityDescription(
    ButtonEntityDescription, ViCareRequiredKeysMixinWithSet
):
    """Describes ViCare button entity."""


@dataclass(frozen=True, kw_only=True)
class ViCareDhwCirculationBoostButtonDescription(ButtonEntityDescription):
    """Describes ViCare DHW circulation boost button entity."""

    duration_minutes: int


BUTTON_DESCRIPTIONS: tuple[ViCareButtonEntityDescription, ...] = (
    ViCareButtonEntityDescription(
        key="activate_onetimecharge",
        translation_key="activate_onetimecharge",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getOneTimeCharge(),
        value_setter=lambda api: api.activateOneTimeCharge(),
    ),
    ViCareButtonEntityDescription(
        key="deactivate_onetimecharge",
        translation_key="deactivate_onetimecharge",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getOneTimeCharge(),
        value_setter=lambda api: api.deactivateOneTimeCharge(),
    ),
)


BOOST_BUTTON_DESCRIPTIONS: tuple[ViCareDhwCirculationBoostButtonDescription, ...] = (
    ViCareDhwCirculationBoostButtonDescription(
        key="dhw_circulation_boost_30m",
        translation_key="dhw_circulation_boost_30m",
        entity_category=EntityCategory.CONFIG,
        duration_minutes=30,
    ),
    ViCareDhwCirculationBoostButtonDescription(
        key="dhw_circulation_boost_60m",
        translation_key="dhw_circulation_boost_60m",
        entity_category=EntityCategory.CONFIG,
        duration_minutes=60,
    ),
)


def _build_entities(
    device_list: list[ViCareDevice],
    min_boost_temperature: float,
    heat_timeout_minutes: int,
    warm_water_delay_minutes: int,
) -> list[ButtonEntity]:
    """Create ViCare button entities for a device."""

    entities: list[ButtonEntity] = []
    for device in device_list:
        entities.extend(
            ViCareButton(
                description,
                get_device_serial(device.api),
                device.config,
                device.api,
            )
            for description in BUTTON_DESCRIPTIONS
            if is_supported(description.key, description.value_getter, device.api)
        )
        if is_supported(
            "getDomesticHotWaterCirculationSchedule",
            lambda api: api.getDomesticHotWaterCirculationSchedule(),
            device.api,
        ):
            entities.extend(
                ViCareDhwCirculationBoostButton(
                    description,
                    get_device_serial(device.api),
                    device.config,
                    device,
                    min_boost_temperature,
                    heat_timeout_minutes,
                    warm_water_delay_minutes,
                )
                for description in BOOST_BUTTON_DESCRIPTIONS
            )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the ViCare button entities."""
    min_boost_temperature = float(
        config_entry.options.get(
            CONF_MIN_BOOST_TEMPERATURE, DEFAULT_DHW_BOOST_MIN_TEMPERATURE
        )
    )
    heat_timeout_minutes = int(
        config_entry.options.get(
            CONF_HEAT_TIMEOUT_MINUTES, DEFAULT_DHW_BOOST_HEAT_TIMEOUT_MINUTES
        )
    )
    warm_water_delay_minutes = int(
        config_entry.options.get(
            CONF_WARM_WATER_DELAY_MINUTES,
            DEFAULT_DHW_BOOST_WARM_WATER_DELAY_MINUTES,
        )
    )
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
            min_boost_temperature,
            heat_timeout_minutes,
            warm_water_delay_minutes,
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


class ViCareDhwCirculationBoostButton(ViCareEntity, ButtonEntity):
    """Representation of a DHW circulation boost button."""

    entity_description: ViCareDhwCirculationBoostButtonDescription

    def __init__(
        self,
        description: ViCareDhwCirculationBoostButtonDescription,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: ViCareDevice,
        min_boost_temperature: float,
        heat_timeout_minutes: int,
        warm_water_delay_minutes: int,
    ) -> None:
        """Initialize the boost button."""
        super().__init__(description.key, device_serial, device_config, device.api)
        self.entity_description = description
        self._device = device
        self._min_boost_temperature = min_boost_temperature
        self._heat_timeout_minutes = heat_timeout_minutes
        self._warm_water_delay_minutes = warm_water_delay_minutes

    async def async_press(self) -> None:
        """Handle the button press."""
        state_map: dict[str, DhwCirculationBoostState] = self.hass.data[
            DOMAIN
        ].setdefault("dhw_circulation_boost", {})
        await async_activate_dhw_circulation_boost(
            self.hass,
            self._device,
            self.entity_description.duration_minutes,
            state_map,
            min_boost_temperature=self._min_boost_temperature,
            heat_timeout_minutes=self._heat_timeout_minutes,
            warm_water_delay_minutes=self._warm_water_delay_minutes,
        )
