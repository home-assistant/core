"""Support for a ScreenLogic number entity."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE

from homeassistant.components.number import (
    DOMAIN,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN, ScreenLogicDataPath, generate_unique_id
from .coordinator import ScreenlogicDataUpdateCoordinator
from .data import (
    DEVICE_INCLUSION_RULES,
    PathPart,
    SupportedValueParameters,
    cleanup_excluded_entity,
    get_ha_unit,
    iterate_expand_group_wildcard,
    preprocess_supported_values,
    realize_path_template,
)
from .entity import ScreenlogicEntity, ScreenLogicEntityDescription

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass
class SupportedNumberValueParametersMixin:
    """Mixin for supported predefined data for a ScreenLogic number entity."""

    set_value_config: tuple[str, tuple[tuple[PathPart | str | int, ...], ...]]
    device_class: NumberDeviceClass | None = None
    entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC


@dataclass
class SupportedNumberValueParameters(
    SupportedValueParameters, SupportedNumberValueParametersMixin
):
    """Supported predefined data for a ScreenLogic number entity."""


SET_SCG_CONFIG_FUNC_DATA = (
    "async_set_scg_config",
    (
        (DEVICE.SCG, GROUP.CONFIGURATION, VALUE.POOL_SETPOINT),
        (DEVICE.SCG, GROUP.CONFIGURATION, VALUE.SPA_SETPOINT),
    ),
)


SUPPORTED_DATA: list[
    tuple[ScreenLogicDataPath, SupportedValueParameters]
] = preprocess_supported_values(
    {
        DEVICE.SCG: {
            GROUP.CONFIGURATION: {
                VALUE.POOL_SETPOINT: SupportedNumberValueParameters(
                    entity_category=EntityCategory.CONFIG,
                    set_value_config=SET_SCG_CONFIG_FUNC_DATA,
                ),
                VALUE.SPA_SETPOINT: SupportedNumberValueParameters(
                    entity_category=EntityCategory.CONFIG,
                    set_value_config=SET_SCG_CONFIG_FUNC_DATA,
                ),
            }
        }
    }
)


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
    data_path: ScreenLogicDataPath
    value_params: SupportedNumberValueParameters
    for data_path, value_params in iterate_expand_group_wildcard(
        gateway, SUPPORTED_DATA
    ):
        entity_key = generate_unique_id(*data_path)

        device = data_path[0]

        if not (DEVICE_INCLUSION_RULES.get(device) or value_params.included).test(
            gateway, data_path
        ):
            cleanup_excluded_entity(coordinator, DOMAIN, entity_key)
            continue

        try:
            value_data = gateway.get_data(*data_path, strict=True)
        except KeyError:
            _LOGGER.debug("Failed to find %s", data_path)
            continue

        set_value_str, set_value_params = value_params.set_value_config
        set_value_func = getattr(gateway, set_value_str)

        entity_kwargs = {
            "data_path": data_path,  #
            "key": entity_key,  #
            "entity_category": value_params.entity_category,
            "entity_registry_enabled_default": value_params.enabled.test(
                gateway, data_path
            ),
            "name": value_data.get(ATTR.NAME),
            "device_class": value_params.device_class,
            "native_unit_of_measurement": get_ha_unit(value_data),
            "native_max_value": value_data.get(ATTR.MAX_SETPOINT),
            "native_min_value": value_data.get(ATTR.MIN_SETPOINT),
            "native_step": value_data.get(ATTR.STEP),
            "set_value": set_value_func,
            "set_value_params": set_value_params,
        }

        entities.append(
            ScreenLogicNumber(
                coordinator,
                ScreenLogicNumberDescription(**entity_kwargs),
            )
        )

    async_add_entities(entities)


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
