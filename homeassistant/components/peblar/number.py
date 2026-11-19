"""Support for Peblar numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from peblar import Peblar, PeblarSetUserConfiguration, PeblarUserConfiguration

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SOLAR_CUSTOM_POWER_MAXIMUM, SOLAR_CUSTOM_POWER_MINIMUM
from .coordinator import (
    PeblarConfigEntry,
    PeblarDataUpdateCoordinator,
    PeblarRuntimeData,
    PeblarUserConfigurationDataUpdateCoordinator,
)
from .entity import PeblarEntity
from .helpers import peblar_exception_handler, supports_custom_solar

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PeblarUserConfigNumberEntityDescription(NumberEntityDescription):
    """Class describing Peblar number entities (user config coordinator)."""

    has_fn: Callable[[PeblarRuntimeData], bool] = lambda x: True
    set_fn: Callable[[Peblar, int], Awaitable[Any]]
    value_fn: Callable[[PeblarUserConfiguration], int | None]


# Both settings are a power on the grid connection, where negative is power
# going out to it. The charger's own web interface takes them typed rather
# than dragged, and so does this: a slider spanning 200 kW is no way to ask
# for a threshold of -1300 W.
USER_CONFIG_DESCRIPTIONS = [
    PeblarUserConfigNumberEntityDescription(
        key="solar_charging_custom_power_threshold",
        translation_key="solar_charging_custom_power_threshold",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_max_value=SOLAR_CUSTOM_POWER_MAXIMUM,
        native_min_value=SOLAR_CUSTOM_POWER_MINIMUM,
        native_step=1,
        native_unit_of_measurement=UnitOfPower.WATT,
        has_fn=lambda x: supports_custom_solar(x.user_configuration_coordinator.data),
        set_fn=lambda peblar, value: peblar.update_user_configuration(
            PeblarSetUserConfiguration(solar_charging_custom_power_threshold=value)
        ),
        value_fn=lambda x: x.solar_charging_custom_power_threshold,
    ),
    PeblarUserConfigNumberEntityDescription(
        key="solar_charging_custom_power_target",
        translation_key="solar_charging_custom_power_target",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_max_value=SOLAR_CUSTOM_POWER_MAXIMUM,
        native_min_value=SOLAR_CUSTOM_POWER_MINIMUM,
        native_step=1,
        native_unit_of_measurement=UnitOfPower.WATT,
        has_fn=lambda x: supports_custom_solar(x.user_configuration_coordinator.data),
        set_fn=lambda peblar, value: peblar.update_user_configuration(
            PeblarSetUserConfiguration(solar_charging_custom_power_target=value)
        ),
        value_fn=lambda x: x.solar_charging_custom_power_target,
    ),
]


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
            ),
            *[
                PeblarUserConfigNumberEntity(
                    entry=entry,
                    coordinator=entry.runtime_data.user_configuration_coordinator,
                    description=description,
                )
                for description in USER_CONFIG_DESCRIPTIONS
                if description.has_fn(entry.runtime_data)
            ],
        ]
    )


class PeblarUserConfigNumberEntity(
    PeblarEntity[PeblarUserConfigurationDataUpdateCoordinator],
    NumberEntity,
):
    """Defines a Peblar number entity backed by the user configuration."""

    entity_description: PeblarUserConfigNumberEntityDescription

    @property
    @override
    def native_value(self) -> int | None:
        """Return the number value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @peblar_exception_handler
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Change to the new number value."""
        await self.entity_description.set_fn(self.coordinator.peblar, int(value))
        await self.coordinator.async_request_refresh()


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
        # Not the user's own charge limit: that is the value being set here,
        # so using it as the ceiling would ratchet the slider down and never
        # let it back up. The charger accepts up to its hardware rating, and
        # reduces anything above the installation limit configured during
        # commissioning, so the lower of the two is what can actually be set.
        configuration = entry.runtime_data.user_configuration_coordinator.data
        self._attr_native_max_value = min(
            entry.runtime_data.system_information.hardware_max_current,
            configuration.current_control_fixed_charge_current_limit,
        )

    @override
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
    @override
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
    @override
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
