"""Support for a ScreenLogic number entity."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.components.number import (
    DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN
from .coordinator import ScreenlogicDataUpdateCoordinator
from .entity import ScreenlogicEntity, ScreenLogicEntityDescription
from .util import cleanup_excluded_entity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass
class ScreenLogicNumberRequiredMixin:
    """Describes a required mixin for a ScreenLogic number entity."""

    set_value: Callable[..., bool] | str
    set_value_params: tuple[tuple[str | int, ...], ...]


@dataclass
class ScreenLogicNumberDescription(
    NumberEntityDescription,
    ScreenLogicEntityDescription,
    ScreenLogicNumberRequiredMixin,
):
    """Describes a ScreenLogic number entity."""


SUPPORTED_SCG_NUMBERS = [
    ScreenLogicNumberDescription(
        set_value="async_set_scg_config",
        set_value_params=(
            (DEVICE.SCG, GROUP.CONFIGURATION, VALUE.POOL_SETPOINT),
            (DEVICE.SCG, GROUP.CONFIGURATION, VALUE.SPA_SETPOINT),
        ),
        data_path=(DEVICE.SCG, GROUP.CONFIGURATION, VALUE.POOL_SETPOINT),
        key=VALUE.POOL_SETPOINT,
        entity_category=EntityCategory.CONFIG,
        name="Pool Chlorinator Setpoint",
        native_max_value=100,
        native_min_value=0,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
    ),
    ScreenLogicNumberDescription(
        set_value="async_set_scg_config",
        set_value_params=(
            (DEVICE.SCG, GROUP.CONFIGURATION, VALUE.POOL_SETPOINT),
            (DEVICE.SCG, GROUP.CONFIGURATION, VALUE.SPA_SETPOINT),
        ),
        data_path=(DEVICE.SCG, GROUP.CONFIGURATION, VALUE.SPA_SETPOINT),
        key=VALUE.SPA_SETPOINT,
        entity_category=EntityCategory.CONFIG,
        name="Spa Chlorinator Setpoint",
        native_max_value=100,
        native_min_value=0,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
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

    scg_number_description: ScreenLogicNumberDescription
    for scg_number_description in SUPPORTED_SCG_NUMBERS:
        if EQUIPMENT_FLAG.CHLORINATOR in gateway.equipment_flags:
            if isinstance(scg_number_description.set_value, str):
                attr = getattr(gateway, scg_number_description.set_value)
                if not callable(attr):
                    raise TypeError(
                        f"{scg_number_description.set_value} is not callable"
                    )
                scg_number_description.set_value = attr
            entities.append(ScreenLogicNumber(coordinator, scg_number_description))
        else:
            _LOGGER.debug(
                "Attempting to cleanup entity '%s'", scg_number_description.key
            )
            cleanup_excluded_entity(coordinator, DOMAIN, scg_number_description.key)

    async_add_entities(entities)


class ScreenLogicNumber(ScreenlogicEntity, NumberEntity):
    """Class to represent a ScreenLogic Number entity."""

    entity_description: ScreenLogicNumberDescription

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        entity_description: ScreenLogicNumberDescription,
    ) -> None:
        """Initialize a ScreenLogic number entity."""
        self._set_value_func = entity_description.set_value
        self._set_value_params = entity_description.set_value_params
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_data[ATTR.VALUE]

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""

        # Current API requires certain values to be set at the same time. This
        # gathers the existing values and updates the particular value being
        # set by this entity.
        args = {}
        for data_path in self._set_value_params:
            data_value = data_path[-1]
            args[data_value] = self.coordinator.gateway.get_value(
                *data_path, strict=True
            )

        args[self._data_key] = value

        assert callable(self._set_value_func)
        if self._set_value_func(*args.values()):
            _LOGGER.debug("Set '%s' to %s", self._data_key, value)
            await self._async_refresh()
        else:
            _LOGGER.debug("Failed to set '%s' to %s", self._data_key, value)
