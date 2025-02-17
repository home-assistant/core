"""Support for Peblar numbers."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    RestoreNumber,
)
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfElectricCurrent,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PeblarConfigEntry, PeblarDataUpdateCoordinator
from .entity import PeblarEntity
from .helpers import peblar_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Peblar number based on a config entry."""
    async_add_entities(
        [
            PeblarChargeCurrentLimitNumberEntity(
                entry=entry,
                coordinator=entry.runtime_data.data_coordinator,
            )
        ]
    )


class PeblarChargeCurrentLimitNumberEntity(
    PeblarEntity[PeblarDataUpdateCoordinator],
    RestoreNumber,
):
    """Defines a Peblar charge current limit number.

    This entity is a little bit different from the other entities, any value
    below 6 amps is ignored. It means the Peblar is not charging.
    Peblar has assigned a dual functionality to the charge current limit
    number, it is used to set the current charging value and to start/stop/pauze
    the charging process.
    """

    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 6
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_translation_key = "charge_current_limit"

    def __init__(
        self,
        entry: PeblarConfigEntry,
        coordinator: PeblarDataUpdateCoordinator,
    ) -> None:
        """Initialize the Peblar charge current limit entity."""
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            description=NumberEntityDescription(key="charge_current_limit"),
        )
        configuration = entry.runtime_data.user_configuration_coordinator.data
        self._attr_native_max_value = configuration.user_defined_charge_limit_current

    async def async_added_to_hass(self) -> None:
        """Load the last known state when adding this entity."""
        if (
            (last_state := await self.async_get_last_state())
            and (last_number_data := await self.async_get_last_number_data())
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and last_number_data.native_value
        ):
            self._attr_native_value = last_number_data.native_value
            # Set the last known charging limit in the runtime data the
            # start/stop/pauze functionality needs it in order to restore
            # the last known charging limits when charging is resumed.
            self.coordinator.config_entry.runtime_data.last_known_charging_limit = int(
                last_number_data.native_value
            )
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update.

        Ignore any update that provides a ampere value that is below the
        minimum value (6 amps). It means the Peblar is currently not charging.
        """
        if (
            current_charge_limit := round(
                self.coordinator.data.ev.charge_current_limit / 1000
            )
        ) < 6:
            return
        self._attr_native_value = current_charge_limit
        # Update the last known charging limit in the runtime data the
        # start/stop/pauze functionality needs it in order to restore
        # the last known charging limits when charging is resumed.
        self.coordinator.config_entry.runtime_data.last_known_charging_limit = (
            current_charge_limit
        )
        super()._handle_coordinator_update()

    @peblar_exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Change the current charging value."""
        # If charging is currently disabled (below 6 amps), just set the value
        # as the native value and the last known charging limit in the runtime
        # data. So we can pick it up once charging gets enabled again.
        if self.coordinator.data.ev.charge_current_limit < 6000:
            self._attr_native_value = int(value)
            self.coordinator.config_entry.runtime_data.last_known_charging_limit = int(
                value
            )
            self.async_write_ha_state()
            return
        await self.coordinator.api.ev_interface(charge_current_limit=int(value) * 1000)
        await self.coordinator.async_request_refresh()
