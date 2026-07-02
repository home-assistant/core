from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MertikConfigEntry
from .const import MODE_THERMO
from .coordinator import MertikDataCoordinator
from .entity import MertikEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MertikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    dataservice = entry.runtime_data
    async_add_entities(
        [
            MertikOnOffSwitchEntity(dataservice, entry.entry_id, entry.data["name"]),
            MertikAuxOnOffSwitchEntity(dataservice, entry.entry_id, entry.data["name"]),
        ]
    )


class MertikOnOffSwitchEntity(MertikEntity, SwitchEntity):
    _attr_name = None
    _attr_icon = "mdi:fireplace"

    def __init__(
        self, dataservice: MertikDataCoordinator, entry_id: str, device_name: str
    ) -> None:
        super().__init__(dataservice, entry_id, device_name)
        self._attr_unique_id = entry_id + "-OnOff"

    @property
    def is_on(self) -> bool:
        return bool(self._dataservice.is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        mode = self._dataservice.heating_mode
        if mode == MODE_THERMO:
            await self.hass.async_add_executor_job(self._dataservice.arm_thermostatic)
        else:
            # mark_optimistic_on first so apply_heating_mode's is_on guard passes.
            self._dataservice.mark_optimistic_on()
            await self.hass.async_add_executor_job(
                self._dataservice.apply_heating_mode, mode
            )
        self._dataservice.async_set_updated_data(None)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self._dataservice.guard_flame_off)
        self._dataservice.mark_optimistic_off()
        self._dataservice.async_set_updated_data(None)


class MertikAuxOnOffSwitchEntity(MertikEntity, SwitchEntity):
    _attr_translation_key = "aux"

    def __init__(
        self, dataservice: MertikDataCoordinator, entry_id: str, device_name: str
    ) -> None:
        super().__init__(dataservice, entry_id, device_name)
        self._attr_unique_id = entry_id + "-AuxOnOff"

    @property
    def is_on(self) -> bool:
        return bool(self._dataservice.is_aux_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self._dataservice.aux_on)
        self._dataservice.async_set_updated_data(None)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self._dataservice.aux_off)
        self._dataservice.async_set_updated_data(None)
