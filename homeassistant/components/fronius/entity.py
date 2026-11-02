"""Base entity for the Fronius integration."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fronius_modbus import Controls, FroniusModbusInverter, Storage

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import SolarNetId

if TYPE_CHECKING:
    from .coordinator import FroniusCoordinatorBase

# the model a writable setting lives in, picked off a discovered inverter
type ModbusComponent = Controls | Storage
type ModbusComponentFn = Callable[[FroniusModbusInverter], ModbusComponent | None]
# the values a Modbus coordinator reads, by entity description key
type ModbusValues = dict[str, float | bool | None]


@dataclass(frozen=True, kw_only=True)
class FroniusEntityDescription[_DataT](EntityDescription):
    """Base class for Fronius entity descriptions.

    ``value_fn`` reads the entity value from the data of one SolarNet device.
    ``exists_fn`` tells whether the device reports the value at all - an
    entity is only added once it does. It defaults to the value not being
    `None`, and is set where the value is derived and may be `None` for a
    reported code, like a message for an undocumented status code.
    """

    value_fn: Callable[[_DataT], object]
    exists_fn: Callable[[_DataT], bool] | None = None

    def exists(self, data: _DataT) -> bool:
        """Return whether the device reports the value of this entity."""
        if self.exists_fn is not None:
            return self.exists_fn(data)
        return self.value_fn(data) is not None


class FroniusEntity(CoordinatorEntity["FroniusCoordinatorBase[Any]"]):
    """Defines a Fronius coordinator entity."""

    entity_description: FroniusEntityDescription[Any]

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FroniusCoordinatorBase[Any],
        description: FroniusEntityDescription[Any],
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius coordinator entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.solar_net_id = solar_net_id
        self._attr_translation_key = description.translation_key or description.key

    def _device_data(self) -> Any:
        """Return the data of this entity's SolarNet device.

        Raises KeyError when the device was not in the latest update.
        """
        return self.coordinator.data[self.solar_net_id]

    def _value(self) -> Any:
        """Return the value of this entity from the latest update.

        Raises KeyError when the device was not in the latest update.
        """
        return self.entity_description.value_fn(self._device_data())


@callback
def async_add_entities_for_seen_keys[
    _CoordinatorT: FroniusCoordinatorBase[Any],
    _DescriptionT: FroniusEntityDescription[Any],
](
    coordinator: _CoordinatorT,
    descriptions: Sequence[_DescriptionT],
    entity_constructor: Callable[[_CoordinatorT, _DescriptionT, SolarNetId], Entity],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for the values a coordinator's devices report.

    An entity is added once its device reports the value, on this update or
    any later one, so values a device only reports at times (e.g. during
    daylight) get their entity when they first appear.
    """
    pending: dict[SolarNetId, list[_DescriptionT]] = {}

    @callback
    def _async_add_new_entities() -> None:
        """Add entities for values reported for the first time."""
        new_entities: list[Entity] = []
        for solar_net_id, device_data in coordinator.data.items():
            if not coordinator.is_identifiable(device_data):
                continue
            remaining: list[_DescriptionT] = []
            for description in pending.setdefault(solar_net_id, list(descriptions)):
                if description.exists(device_data):
                    new_entities.append(
                        entity_constructor(coordinator, description, solar_net_id)
                    )
                else:
                    remaining.append(description)
            pending[solar_net_id] = remaining
        async_add_entities(new_entities)

    _async_add_new_entities()
    coordinator.config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_entities)
    )
