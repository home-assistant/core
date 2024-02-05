"""Support for a ScreenLogic number entity."""
from dataclasses import dataclass
import logging

from screenlogicpy.const.common import ScreenLogicCommunicationError, ScreenLogicError
from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.components.number import (
    DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN
from .coordinator import ScreenlogicDataUpdateCoordinator
from .entity import ScreenLogicEntity, ScreenLogicEntityDescription
from .util import cleanup_excluded_entity, get_ha_unit

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True)
class ScreenLogicNumberDescription(
    NumberEntityDescription,
    ScreenLogicEntityDescription,
):
    """Describes a ScreenLogic number entity."""


SUPPORTED_SCG_NUMBERS = [
    ScreenLogicNumberDescription(
        data_root=(DEVICE.SCG, GROUP.CONFIGURATION),
        key=VALUE.POOL_SETPOINT,
        entity_category=EntityCategory.CONFIG,
    ),
    ScreenLogicNumberDescription(
        data_root=(DEVICE.SCG, GROUP.CONFIGURATION),
        key=VALUE.SPA_SETPOINT,
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities: list[ScreenLogicNumber] = []
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[SL_DOMAIN][
        config_entry.entry_id
    ]
    gateway = coordinator.gateway

    for scg_number_description in SUPPORTED_SCG_NUMBERS:
        scg_number_data_path = (
            *scg_number_description.data_root,
            scg_number_description.key,
        )
        if EQUIPMENT_FLAG.CHLORINATOR not in gateway.equipment_flags:
            cleanup_excluded_entity(coordinator, DOMAIN, scg_number_data_path)
            continue
        if gateway.get_data(*scg_number_data_path):
            entities.append(ScreenLogicSCGNumber(coordinator, scg_number_description))

    async_add_entities(entities)


class ScreenLogicNumber(ScreenLogicEntity, NumberEntity):
    """Base class to represent a ScreenLogic Number entity."""

    entity_description: ScreenLogicNumberDescription

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        entity_description: ScreenLogicNumberDescription,
    ) -> None:
        """Initialize a ScreenLogic number entity."""
        super().__init__(coordinator, entity_description)

        self._attr_native_unit_of_measurement = get_ha_unit(
            self.entity_data.get(ATTR.UNIT)
        )
        if entity_description.native_max_value is None and isinstance(
            max_val := self.entity_data.get(ATTR.MAX_SETPOINT), int | float
        ):
            self._attr_native_max_value = max_val
        if entity_description.native_min_value is None and isinstance(
            min_val := self.entity_data.get(ATTR.MIN_SETPOINT), int | float
        ):
            self._attr_native_min_value = min_val
        if entity_description.native_step is None and isinstance(
            step := self.entity_data.get(ATTR.STEP), int | float
        ):
            self._attr_native_step = step

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_data[ATTR.VALUE]

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        raise NotImplementedError()


class ScreenLogicSCGNumber(ScreenLogicNumber):
    """Class to represent a ScreenLoigic SCG Number entity."""

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""

        # Current API requires int values for the currently supported numbers.
        value = int(value)

        try:
            await self.gateway.async_set_scg_config(**{self._data_key: value})
        except (ScreenLogicCommunicationError, ScreenLogicError) as sle:
            raise HomeAssistantError(
                f"Failed to set '{self._data_key}' to {value}: {sle.msg}"
            ) from sle
        _LOGGER.debug("Set '%s' to %s", self._data_key, value)
        await self._async_refresh()
