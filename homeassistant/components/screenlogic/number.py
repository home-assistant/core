"""Support for a ScreenLogic number entity."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE

from homeassistant.components.number import (
    DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN
from .coordinator import ScreenlogicDataUpdateCoordinator
from .data import (
    EntityParameter,
    SupportedDeviceDescriptions,
    get_ha_unit,
    process_supported_values,
    realize_path_template,
)
from .entity import ScreenlogicEntity, ScreenLogicEntityDescription

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


SET_SCG_CONFIG_FUNC_DATA = (
    "async_set_scg_config",
    (
        (DEVICE.SCG, GROUP.CONFIGURATION, VALUE.POOL_SETPOINT),
        (DEVICE.SCG, GROUP.CONFIGURATION, VALUE.SPA_SETPOINT),
    ),
)


SUPPORTED_DATA: SupportedDeviceDescriptions = {
    DEVICE.SCG: {
        GROUP.CONFIGURATION: {
            VALUE.POOL_SETPOINT: {
                EntityParameter.ENTITY_CATEGORY: EntityCategory.CONFIG,
                EntityParameter.SET_VALUE: SET_SCG_CONFIG_FUNC_DATA,
            },
            VALUE.SPA_SETPOINT: {
                EntityParameter.ENTITY_CATEGORY: EntityCategory.CONFIG,
                EntityParameter.SET_VALUE: SET_SCG_CONFIG_FUNC_DATA,
            },
        }
    }
}


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

    for base_kwargs, base_data in process_supported_values(
        coordinator, DOMAIN, SUPPORTED_DATA
    ):
        if set_value_data := base_data.value_parameters.get(EntityParameter.SET_VALUE):
            set_value_str, set_value_params = set_value_data
            set_value_func = getattr(gateway, set_value_str)
        base_kwargs["native_unit_of_measurement"] = get_ha_unit(base_data.value_data)
        base_kwargs["native_max_value"] = base_data.value_data.get(ATTR.MAX_SETPOINT)
        base_kwargs["native_min_value"] = base_data.value_data.get(ATTR.MIN_SETPOINT)
        base_kwargs["native_step"] = base_data.value_data.get(ATTR.STEP)
        base_kwargs["set_value"] = set_value_func
        base_kwargs["set_value_params"] = set_value_params

        entities.append(
            ScreenLogicNumber(
                coordinator,
                ScreenLogicNumberDescription(**base_kwargs),
            )
        )

    async_add_entities(entities)


SUPPORTED_SCG_NUMBERS = (
    VALUE.POOL_SETPOINT,
    VALUE.SPA_SETPOINT,
)


@dataclass
class ScreenLogicNumberRequiredMixin:
    """Describes a required mixin for a ScreenLogic number entity."""

    set_value: Callable[..., bool]
    set_value_params: tuple[tuple[str | int, ...], ...]


@dataclass
class ScreenLogicNumberDescription(
    NumberEntityDescription,
    ScreenLogicEntityDescription,
    ScreenLogicNumberRequiredMixin,
):
    """Describes a ScreenLogic number entity."""


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
            data_path = realize_path_template(data_path, self._data_path)
            data_value = data_path[-1]
            args[data_value] = self.coordinator.gateway.get_value(
                *data_path, strict=True
            )

        args[self._data_key] = value

        if self._set_value_func(*args.values()):
            _LOGGER.debug("Set '%s' to %s", self._data_key, value)
            await self._async_refresh()
        else:
            _LOGGER.debug("Failed to set '%s' to %s", self._data_key, value)
