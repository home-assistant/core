"""Support for Modbus Coil and Discrete Input sensors."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_hub
from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CONF_SLAVE_COUNT,
    CONF_VIRTUAL_COUNT,
)
from .entity import BasePlatform
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Modbus binary sensors."""

    if discovery_info is None:
        return

    sensors: list[ModbusBinarySensor | SlaveSensor] = []
    hub = get_hub(hass, discovery_info[CONF_NAME])
    for entry in discovery_info[CONF_BINARY_SENSORS]:
        slave_count = entry.get(CONF_SLAVE_COUNT, None) or entry.get(
            CONF_VIRTUAL_COUNT, 0
        )
        sensor = ModbusBinarySensor(hass, hub, entry, slave_count)
        if slave_count > 0:
            sensors.extend(await sensor.async_setup_slaves(hass, slave_count, entry))
        sensors.append(sensor)
    async_add_entities(sensors)


class ModbusBinarySensor(BasePlatform, RestoreEntity, BinarySensorEntity):
    """Modbus binary sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: ModbusHub,
        entry: dict[str, Any],
        slave_count: int,
    ) -> None:
        """Initialize the Modbus binary sensor."""
        self._count = slave_count + 1
        self._coordinator: DataUpdateCoordinator[list[int] | None] | None = None
        self._result: list[int] = []
        super().__init__(hass, hub, entry)

    async def async_setup_slaves(
        self, hass: HomeAssistant, slave_count: int, entry: dict[str, Any]
    ) -> list[SlaveSensor]:
        """Add slaves as needed (1 read for multiple sensors)."""

        # Add a dataCoordinator for each sensor that have slaves
        # this ensures that idx = bit position of value in result
        # polling is done with the base class
        name = self._attr_name if self._attr_name else "modbus_sensor"
        self._coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=name,
        )

        return [
            SlaveSensor(self._coordinator, idx, entry) for idx in range(slave_count)
        ]

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        if state := await self.async_get_last_state():
            self._attr_is_on = state.state == STATE_ON

    async def async_update(self, now: datetime | None = None) -> None:
        """Update the state of the sensor."""

        # do not allow multiple active calls to the same platform
        if self._call_active:
            return
        self._call_active = True
        result = await self._hub.async_pb_call(
            self._slave, self._address, self._count, self._input_type
        )
        self._call_active = False
        if result is None:
            self._attr_available = False
            self._result = []
        else:
            self._attr_available = True
            if self._input_type in (CALL_TYPE_COIL, CALL_TYPE_DISCRETE):
                self._result = result.bits
            else:
                self._result = result.registers
            self._attr_is_on = bool(self._result[0] & 1)

        self.async_write_ha_state()
        if self._coordinator:
            self._coordinator.async_set_updated_data(self._result)


class SlaveSensor(
    CoordinatorEntity[DataUpdateCoordinator[list[int] | None]],
    RestoreEntity,
    BinarySensorEntity,
):
    """Modbus slave binary sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[list[int] | None],
        idx: int,
        entry: dict[str, Any],
    ) -> None:
        """Initialize the Modbus binary sensor."""
        idx += 1
        self._attr_name = f"{entry[CONF_NAME]} {idx}"
        self._attr_device_class = entry.get(CONF_DEVICE_CLASS)
        self._attr_unique_id = entry.get(CONF_UNIQUE_ID)
        if self._attr_unique_id:
            self._attr_unique_id = f"{self._attr_unique_id}_{idx}"
        self._attr_available = False
        self._result_inx = idx
        super().__init__(coordinator)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        if state := await self.async_get_last_state():
            self._attr_is_on = state.state == STATE_ON
            self.async_write_ha_state()
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        result = self.coordinator.data
        self._attr_is_on = bool(result[self._result_inx] & 1) if result else None
        super()._handle_coordinator_update()
