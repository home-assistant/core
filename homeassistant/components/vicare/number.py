"""Number for ViCare."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging
from typing import Any

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceWithComponent,
)
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
from requests.exceptions import ConnectionError as RequestConnectionError

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ViCareRequiredKeysMixin
from .const import DOMAIN, VICARE_API, VICARE_DEVICE_CONFIG
from .entity import ViCareEntity
from .utils import is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass
class ViCareNumberEntityDescription(NumberEntityDescription, ViCareRequiredKeysMixin):
    """Describes ViCare number entity."""

    value_setter: Callable[[PyViCareDevice, float], Any | None] | None = None
    min_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    max_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    stepping_getter: Callable[[PyViCareDevice], float | None] | None = None


PROGRAM_ENTITY_DESCRIPTIONS: tuple[ViCareNumberEntityDescription, ...] = (
    ViCareNumberEntityDescription(
        key="normal_temperature",
        translation_key="normal_temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram("normal"),
        value_setter=lambda api, value: api.setProgramTemperature("normal", value),
        min_value_getter=lambda api: api.getProgramMinTemperature("normal"),
        max_value_getter=lambda api: api.getProgramMaxTemperature("normal"),
        stepping_getter=lambda api: api.getProgramStepping("normal"),
    ),
    ViCareNumberEntityDescription(
        key="reduced_temperature",
        translation_key="reduced_temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram("reduced"),
        value_setter=lambda api, value: api.setProgramTemperature("reduced", value),
        min_value_getter=lambda api: api.getProgramMinTemperature("reduced"),
        max_value_getter=lambda api: api.getProgramMaxTemperature("reduced"),
        stepping_getter=lambda api: api.getProgramStepping("reduced"),
    ),
    ViCareNumberEntityDescription(
        key="comfort_temperature",
        translation_key="comfort_temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram("comfort"),
        value_setter=lambda api, value: api.setProgramTemperature("comfort", value),
        min_value_getter=lambda api: api.getProgramMinTemperature("comfort"),
        max_value_getter=lambda api: api.getProgramMaxTemperature("comfort"),
        stepping_getter=lambda api: api.getProgramStepping("comfort"),
    ),
)


def _build_entity(
    name: str,
    vicare_api: PyViCareHeatingDeviceWithComponent,
    device_config: PyViCareDeviceConfig,
    entity_description: ViCareNumberEntityDescription,
) -> ViCareNumber | None:
    """Create a ViCare number entity."""
    if is_supported(name, entity_description, vicare_api):
        _LOGGER.debug("Found device %s", name)
        return ViCareNumber(
            name,
            vicare_api,
            device_config,
            entity_description,
        )
    return None


async def _entities_from_descriptions(
    hass: HomeAssistant,
    entities: list[ViCareNumber],
    iterables: list[PyViCareHeatingDeviceWithComponent],
    config_entry: ConfigEntry,
) -> None:
    """Create entities from descriptions and list of circuits."""
    for current in iterables:
        suffix = ""
        if len(iterables) > 1:
            suffix = f" {current.id}"

        for description in PROGRAM_ENTITY_DESCRIPTIONS:
            entity = await hass.async_add_executor_job(
                _build_entity,
                f"{description.name}{suffix}",
                current,
                hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG],
                description,
            )
            if entity is not None:
                entities.append(entity)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare number devices."""
    api = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]

    entities: list[ViCareNumber] = []
    try:
        await _entities_from_descriptions(hass, entities, api.circuits, config_entry)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.debug("No circuits found")

    async_add_entities(entities)


class ViCareNumber(ViCareEntity, NumberEntity):
    """Representation of a ViCare number."""

    entity_description: ViCareNumberEntityDescription

    def __init__(
        self,
        name: str,
        api: PyViCareHeatingDeviceWithComponent,
        device_config: PyViCareDeviceConfig,
        description: ViCareNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(device_config, api, description.key)
        self.entity_description = description
        self._attr_name = name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.value_setter:
            await self.hass.async_add_executor_job(
                self.entity_description.value_setter, self._api, value
            )
        self.async_write_ha_state()

    def update(self) -> None:
        """Update state of number."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                value = self.entity_description.value_getter(self._api)
                if value is not None:
                    self._attr_native_value = float(value)

                if self.entity_description.min_value_getter:
                    min_value = self.entity_description.min_value_getter(self._api)
                    if min_value is not None:
                        self._attr_native_min_value = min_value

                if self.entity_description.max_value_getter:
                    max_value = self.entity_description.max_value_getter(self._api)
                    if max_value is not None:
                        self._attr_native_max_value = max_value

                if self.entity_description.stepping_getter:
                    stepping = self.entity_description.stepping_getter(self._api)
                    if stepping is not None:
                        self._attr_native_step = stepping
        except RequestConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
