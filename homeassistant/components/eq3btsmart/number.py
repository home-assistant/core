"""Platform for eQ-3 number entities."""

from datetime import timedelta

from eq3btsmart import Thermostat
from eq3btsmart.const import (
    EQ3BT_MAX_OFFSET,
    EQ3BT_MAX_TEMP,
    EQ3BT_MIN_OFFSET,
    EQ3BT_MIN_TEMP,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry, UndefinedType
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_NAME_AWAY_HOURS,
    ENTITY_NAME_AWAY_TEMPERATURE,
    ENTITY_NAME_COMFORT,
    ENTITY_NAME_ECO,
    ENTITY_NAME_OFFSET,
    ENTITY_NAME_WINDOW_OPEN_TEMPERATURE,
    ENTITY_NAME_WINDOW_OPEN_TIMEOUT,
)
from .eq3_entity import Eq3Entity
from .models import Eq3Config, Eq3ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Handle config entry setup."""

    eq3_config_entry: Eq3ConfigEntry = hass.data[DOMAIN][config_entry.entry_id]
    thermostat = eq3_config_entry.thermostat
    eq3_config = eq3_config_entry.eq3_config

    new_devices = [
        ComfortTemperature(eq3_config, thermostat),
        EcoTemperature(eq3_config, thermostat),
        OffsetTemperature(eq3_config, thermostat),
        WindowOpenTemperature(eq3_config, thermostat),
        WindowOpenTimeout(eq3_config, thermostat),
        AwayForHours(eq3_config, thermostat),
        AwayTemperature(eq3_config, thermostat),
    ]
    async_add_entities(new_devices)


class Base(Eq3Entity, NumberEntity):
    """Base class for all eQ-3 number entities."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the base class."""

        super().__init__(eq3_config, thermostat)

        self._thermostat.register_update_callback(self.schedule_update_ha_state)
        self._attr_has_entity_name = True
        self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_native_min_value = EQ3BT_MIN_TEMP
        self._attr_native_max_value = EQ3BT_MAX_TEMP

        self._attr_native_step = 0.5
        self._attr_mode = NumberMode.BOX

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""

        if self.name is None or isinstance(self.name, UndefinedType):
            return None

        return format_mac(self._eq3_config.mac_address) + "_" + self.name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this eQ-3 device."""

        return DeviceInfo(
            identifiers={(DOMAIN, self._eq3_config.mac_address)},
        )


class ComfortTemperature(Base):
    """Number entity for the comfort temperature."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the comfort temperature."""

        super().__init__(eq3_config, thermostat)

        self._attr_name = ENTITY_NAME_COMFORT

    @property
    def native_value(self) -> float | None:
        """Return the current comfort temperature."""

        if self._thermostat.status is None or self._thermostat.status.presets is None:
            return None

        return self._thermostat.status.presets.comfort_temperature.value

    async def async_set_native_value(self, value: float) -> None:
        """Set the comfort temperature."""

        await self._thermostat.async_get_status()
        await self._thermostat.async_configure_presets(comfort_temperature=value)


class EcoTemperature(Base):
    """Number entity for the eco temperature."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the eco temperature."""

        super().__init__(eq3_config, thermostat)

        self._attr_name = ENTITY_NAME_ECO

    @property
    def native_value(self) -> float | None:
        """Return the current eco temperature."""

        if self._thermostat.status is None or self._thermostat.status.presets is None:
            return None

        return self._thermostat.status.presets.eco_temperature.value

    async def async_set_native_value(self, value: float) -> None:
        """Set the eco temperature."""

        await self._thermostat.async_get_status()
        await self._thermostat.async_configure_presets(eco_temperature=value)


class OffsetTemperature(Base):
    """Number entity for the temperature offset."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the temperature offset."""

        super().__init__(eq3_config, thermostat)

        self._attr_name = ENTITY_NAME_OFFSET
        self._attr_native_min_value = EQ3BT_MIN_OFFSET
        self._attr_native_max_value = EQ3BT_MAX_OFFSET

    @property
    def native_value(self) -> float | None:
        """Return the current temperature offset."""

        if self._thermostat.status is None or self._thermostat.status.presets is None:
            return None

        return self._thermostat.status.presets.offset_temperature.value

    async def async_set_native_value(self, value: float) -> None:
        """Set the temperature offset."""

        await self._thermostat.async_configure_temperature_offset(value)


class WindowOpenTemperature(Base):
    """Number entity for the window open temperature."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the window open temperature."""

        super().__init__(eq3_config, thermostat)

        self._attr_name = ENTITY_NAME_WINDOW_OPEN_TEMPERATURE

    @property
    def native_value(self) -> float | None:
        """Return the current window open temperature."""

        if self._thermostat.status is None or self._thermostat.status.presets is None:
            return None

        return self._thermostat.status.presets.window_open_temperature.value

    async def async_set_native_value(self, value: float) -> None:
        """Set the window open temperature."""

        await (
            self._thermostat.async_get_status()
        )  # to ensure the other value is up to date

        if self._thermostat.status is None or self._thermostat.status.presets is None:
            return

        await self._thermostat.async_configure_window_open(
            temperature=value,
            duration=self._thermostat.status.presets.window_open_time.value,
        )

        await self._thermostat.async_configure_window_open(
            temperature=value,
            duration=self._thermostat.status.presets.window_open_time.value,
        )


class WindowOpenTimeout(Base):
    """Number entity for the window open timeout."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the window open timeout."""

        super().__init__(eq3_config, thermostat)

        self._thermostat.register_update_callback(self.schedule_update_ha_state)
        self._attr_has_entity_name = True
        self._attr_mode = NumberMode.BOX
        self._attr_name = ENTITY_NAME_WINDOW_OPEN_TIMEOUT
        self._attr_native_min_value = 0
        self._attr_native_max_value = 60
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES

    @property
    def native_value(self) -> float | None:
        """Return the current window open timeout."""

        if self._thermostat.status is None or self._thermostat.status.presets is None:
            return None

        return (
            self._thermostat.status.presets.window_open_time.value.total_seconds() / 60
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the window open timeout."""

        await (
            self._thermostat.async_get_status()
        )  # to ensure the other value is up to date

        if self._thermostat.status is None or self._thermostat.status.presets is None:
            return

        await self._thermostat.async_configure_window_open(
            temperature=self._thermostat.status.presets.window_open_temperature.value,
            duration=timedelta(minutes=value),
        )


class AwayForHours(Base, RestoreNumber):
    """Number entity for the away hours."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the away hours."""

        super().__init__(eq3_config, thermostat)

        self._attr_has_entity_name = True
        self._attr_mode = NumberMode.BOX
        self._attr_name = ENTITY_NAME_AWAY_HOURS
        self._attr_native_min_value = 0.5
        self._attr_native_max_value = 1000000
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS

    async def async_added_to_hass(self) -> None:
        """Restore last state."""

        data = await self.async_get_last_number_data()
        if data and data.native_value is not None:
            self._eq3_config.default_away_hours = data.native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the away hours."""

        self._eq3_config.default_away_hours = value

    @property
    def native_value(self) -> float | None:
        """Return the current away hours."""

        return self._eq3_config.default_away_hours


class AwayTemperature(Base, RestoreNumber):
    """Number entity for the away temperature."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the away temperature."""

        super().__init__(eq3_config, thermostat)

        self._attr_name = ENTITY_NAME_AWAY_TEMPERATURE

    async def async_added_to_hass(self) -> None:
        """Restore last state."""

        data = await self.async_get_last_number_data()
        if data and data.native_value is not None:
            self._eq3_config.default_away_temperature = data.native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the away temperature."""

        self._eq3_config.default_away_temperature = value

    @property
    def native_value(self) -> float | None:
        """Return the current away temperature."""

        return self._eq3_config.default_away_temperature
