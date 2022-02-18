"""TOLO Sauna number controls."""
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToloSaunaCoordinatorEntity, ToloSaunaUpdateCoordinator
from .const import DOMAIN, FAN_TIMER_MAX, POWER_TIMER_MAX, SALT_BATH_TIMER_MAX


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number controls for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ToloPowerTimerDuration(coordinator, entry),
            ToloSaltBathTimerDuration(coordinator, entry),
            ToloFanTimerDuration(coordinator, entry),
        ]
    )


class ToloPowerTimerDuration(ToloSaunaCoordinatorEntity, NumberEntity):
    """
    TOLO Sauna Power Timer Control.

    Automatic shuts down the device after configured timeout.
    """

    _attr_name = "Power Timer"
    _attr_min_value = 0
    _attr_max_value = POWER_TIMER_MAX
    _attr_step = 1
    _attr_icon = "mdi:power-settings"

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Power Timer Duration entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_power_timer_duration"

    @property
    def value(self) -> float:
        """Return current power timer setting."""
        return self.coordinator.data.settings.power_timer or 0

    def set_value(self, value: float) -> None:
        """Set power timeout. 0 = disabled."""
        int_value = int(value)
        if int_value == 0:
            self.coordinator.client.set_power_timer(None)
            return
        self.coordinator.client.set_power_timer(int_value)


class ToloSaltBathTimerDuration(ToloSaunaCoordinatorEntity, NumberEntity):
    """
    TOLO Sauna Salt Bath Timer Control.

    Activates the salt sprayer in the configured interval.
    """

    _attr_name = "Salt Bath Timer"
    _attr_min_value = 0
    _attr_max_value = SALT_BATH_TIMER_MAX
    _attr_step = 1
    _attr_icon = "mdi:shaker-outline"

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Salt Bath Timer Duration entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_salt_bath_timer_duration"

    @property
    def value(self) -> float:
        """Return current salt bath timer setting."""
        return self.coordinator.data.settings.salt_bath_timer or 0

    def set_value(self, value: float) -> None:
        """Set the salt bath spray interval. 0 = disabled."""
        int_value = int(value)
        if int_value == 0:
            self.coordinator.client.set_salt_bath_timer(None)
            return
        self.coordinator.client.set_salt_bath_timer(int_value)


class ToloFanTimerDuration(ToloSaunaCoordinatorEntity, NumberEntity):
    """
    TOLO Sauna Fan Timer Control.

    Deactivate the fan after the configured timeout.
    """

    _attr_name = "Fan Timer"
    _attr_min_value = 0
    _attr_max_value = FAN_TIMER_MAX
    _attr_step = 1
    _attr_icon = "mdi:fan-auto"

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Salt Bath Timer Duration entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_fan_timer_duration"

    @property
    def value(self) -> float:
        """Return current fan timer setting."""
        return self.coordinator.data.settings.fan_timer or 0

    def set_value(self, value: float) -> None:
        """Set Fan timer. 0 = no automatic shutdown."""
        int_value = int(value)
        if int_value == 0:
            self.coordinator.client.set_fan_timer(None)
            return
        self.coordinator.client.set_fan_timer(int_value)
