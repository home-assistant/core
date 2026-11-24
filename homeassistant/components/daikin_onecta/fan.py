"""Support for Daikin air purifiers."""

from typing import Any, override

from daikin_onecta.client import OnectaClient
from daikin_onecta.models import AirPurification, FanSpeedMode

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import FANMODE_FIXED
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .discovery import (
    has_air_purifier_power,
    has_air_purifier_power_control,
    has_climate_entity,
)
from .entity import (
    DaikinManagementPointEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    present_devices,
)
from .utils import enum_value_to_state, fixed_positions, management_point_unique_id

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin air-purifier fan entities."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        hass,
        config_entry,
        coordinator,
        async_add_entities,
        lambda is_known: _create_air_purifiers(coordinator, is_known),
    )


def _create_air_purifiers(
    coordinator: OnectaDataUpdateCoordinator,
    is_known: EntityIdChecker,
) -> list[DaikinAirPurifier]:
    """Create supported air purifiers from the current cloud model."""
    entities: list[DaikinAirPurifier] = []
    for device in present_devices(coordinator):
        entities.extend(
            DaikinAirPurifier(device, management_point.embedded_id, coordinator)
            for management_point in device.device.management_points_by_type(
                "climateControl"
            )
            if has_air_purifier_power(management_point)
            and not has_climate_entity(management_point)
            and not is_known(
                Platform.FAN,
                management_point_unique_id(
                    device.id, management_point.embedded_id, "air_purifier"
                ),
            )
        )
    return entities


class DaikinAirPurifier(DaikinManagementPointEntity, FanEntity):
    """Representation of a Daikin air purifier."""

    _attr_name = None
    _attr_translation_key = "air_purifier"

    def __init__(
        self,
        device: DaikinOnectaDevice,
        embedded_id: str,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """Initialize the air purifier."""
        super().__init__(device, coordinator, embedded_id)
        self._attr_unique_id = management_point_unique_id(
            device.id, embedded_id, "air_purifier"
        )
        self.update_state()

    def _air_purification(self) -> AirPurification | None:
        """Return the typed air-purification state view."""
        management_point = self._management_point
        return (
            management_point.air_purification if management_point is not None else None
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the cached Daikin power state, including unknown values."""
        return self._attr_is_on

    def _fixed_speeds(self, mode: str | None = None) -> list[int]:
        """Return the current mode's ordered writable fixed speeds."""
        fixed = self._fixed_speed_characteristic(mode)
        if fixed is None or not fixed.settable:
            return []
        return list(fixed_positions(fixed) or ())

    def _fixed_speed_characteristic(
        self, mode: str | None = None
    ) -> FanSpeedMode | None:
        """Return the current mode's fixed-speed characteristic."""
        purification = self._air_purification()
        operation = (
            purification.fan_operation(mode) if purification is not None else None
        )
        return (
            operation.fan_speed.modes.get(FANMODE_FIXED)
            if operation and operation.fan_speed and operation.fan_speed.modes
            else None
        )

    def _power_control_is_available(self) -> bool:
        """Return whether the air purifier power control is writable."""
        return has_air_purifier_power_control(self._management_point)

    @property
    @override
    def available(self) -> bool:
        """Return whether this point is still owned by the purifier fan."""
        management_point = self._management_point
        return (
            super().available
            and self._power_control_is_available()
            and management_point is not None
            and not has_climate_entity(management_point)
        )

    @override
    def update_state(self) -> None:
        """Refresh entity state from typed purifier data."""
        purification = self._air_purification()
        if purification is None:
            self._attr_is_on = None
            self._attr_preset_mode = None
            self._attr_preset_modes = []
            self._attr_percentage = None
            self._attr_speed_count = 100
            self._attr_supported_features = FanEntityFeature(0)
            return
        power = purification.power
        is_on = (
            power.value == "on"
            if power is not None and power.value is not None
            else None
        )
        self._attr_is_on = is_on
        mode = purification.mode
        self._attr_preset_mode = (
            enum_value_to_state(mode.value)
            if mode is not None and mode.value not in (None, "manualFan")
            else None
        )
        self._attr_preset_modes = (
            [
                enum_value_to_state(preset)
                for preset in purification.modes
                if preset not in (None, "manualFan")
            ]
            if mode and mode.settable
            else []
        )
        fixed_speeds = self._fixed_speeds("manualFan")
        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if self._attr_preset_modes:
            features |= FanEntityFeature.PRESET_MODE
        if fixed_speeds and mode and (mode.settable or mode.value == "manualFan"):
            features |= FanEntityFeature.SET_SPEED
        self._attr_speed_count = len(fixed_speeds) or 100
        self._attr_percentage = 0 if is_on is False else None
        if is_on and mode is not None and mode.value == "manualFan" and fixed_speeds:
            fixed = self._fixed_speed_characteristic()
            fixed_speed = fixed.value if fixed is not None else None
            if fixed_speed is not None and fixed_speed in fixed_speeds:
                self._attr_percentage = ordered_list_item_to_percentage(
                    fixed_speeds, fixed_speed
                )
        self._attr_supported_features = features

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the air purifier."""
        if preset_mode is not None and percentage is not None:
            self._raise_service_validation_error("air_purifier_preset_and_percentage")
        if not self._power_control_is_available():
            self._raise_service_validation_error("air_purifier_power_unavailable")
        if self.is_on is None:
            self._raise_service_validation_error("air_purifier_power_unavailable")
        native_preset = (
            self._native_preset_mode(preset_mode) if preset_mode is not None else None
        )
        if percentage is not None:
            self._validate_percentage(percentage)
            if percentage == 0:
                await self.async_set_percentage(percentage)
                return
        if not self.is_on:
            await self._async_execute_sub_client_command(
                OnectaClient.air_purification,
                lambda purifier: purifier.set_power(True),
                "air_purifier_turn_on_failed",
            )
            purification = self._air_purification()
            if purification is not None and purification.power is not None:
                purification.power.value = "on"
            self._publish_write_update()
        if native_preset is not None:
            await self._async_set_mode(native_preset)
        if percentage is not None:
            await self.async_set_percentage(percentage)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the air purifier."""
        if not self._power_control_is_available():
            self._raise_service_validation_error("air_purifier_power_unavailable")
        if self.is_on is None:
            self._raise_service_validation_error("air_purifier_power_unavailable")
        if not self.is_on:
            return
        await self._async_execute_sub_client_command(
            OnectaClient.air_purification,
            lambda purifier: purifier.set_power(False),
            "air_purifier_turn_off_failed",
        )
        purification = self._air_purification()
        if purification is not None and purification.power is not None:
            purification.power.value = "off"
        self._publish_write_update()

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Select an automatic air-purification preset, not a manual speed."""
        await self._async_set_mode(self._native_preset_mode(preset_mode))

    def _native_preset_mode(self, preset_mode: str) -> str:
        """Validate and return the Daikin mode represented by a HA preset."""
        purification = self._air_purification()
        native_mode = (
            next(
                (
                    mode
                    for mode in purification.modes
                    if (
                        mode not in (None, "manualFan")
                        and enum_value_to_state(mode) == preset_mode
                    )
                ),
                None,
            )
            if purification is not None
            else None
        )
        if native_mode is None:
            self._raise_service_validation_error("air_purifier_mode_unavailable")
        self._validate_mode(native_mode)
        return native_mode

    def _validate_mode(self, mode: str) -> None:
        """Validate that Daikin currently allows the requested mode."""
        purification = self._air_purification()
        if (
            purification is None
            or purification.mode is None
            or not purification.mode.settable
            or mode not in purification.modes
        ):
            self._raise_service_validation_error("air_purifier_mode_unavailable")

    def _validate_percentage(self, percentage: int) -> None:
        """Validate that a manual speed is currently available."""
        if percentage == 0:
            return
        purification = self._air_purification()
        if purification is None or purification.mode is None:
            self._raise_service_validation_error("air_purifier_speed_unavailable")
        if self.is_on is None:
            self._raise_service_validation_error("air_purifier_power_unavailable")
        if not self._fixed_speeds("manualFan"):
            self._raise_service_validation_error("air_purifier_speed_unavailable")
        if purification.mode.value != "manualFan" and (
            not purification.mode.settable or "manualFan" not in purification.modes
        ):
            self._raise_service_validation_error("air_purifier_mode_unavailable")

    async def _async_set_mode(self, mode: str) -> None:
        """Select a native mode, including manual mode for percentage commands."""
        purification = self._air_purification()
        self._validate_mode(mode)
        if purification is None or purification.mode is None:
            self._raise_service_validation_error("air_purifier_mode_unavailable")
        if mode == purification.mode.value:
            return
        await self._async_execute_sub_client_command(
            OnectaClient.air_purification,
            lambda purifier: purifier.set_mode(mode),
            "air_purifier_set_mode_failed",
        )
        purification = self._air_purification()
        if purification is not None and purification.mode is not None:
            purification.mode.value = mode
        self._publish_write_update()

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the current mode's fixed fan speed."""
        self._validate_percentage(percentage)
        if percentage == 0:
            await self.async_turn_off()
            return
        if not self.is_on:
            await self.async_turn_on()
        purification = self._air_purification()
        if purification is None or purification.mode is None:
            self._raise_service_validation_error("air_purifier_speed_unavailable")
        if purification.mode.value != "manualFan":
            await self._async_set_mode("manualFan")
        purification = self._air_purification()
        if purification is None or purification.mode is None:
            self._raise_service_validation_error("air_purifier_speed_unavailable")
        speeds = self._fixed_speeds("manualFan")
        if not speeds:
            self._raise_service_validation_error("air_purifier_speed_unavailable")
        speed = percentage_to_ordered_list_item(speeds, percentage)
        fixed = self._fixed_speed_characteristic("manualFan")
        if fixed is not None and fixed.value == speed:
            return
        await self._async_execute_sub_client_command(
            OnectaClient.air_purification,
            lambda purifier: purifier.set_fixed_fan_speed("manualFan", speed),
            "air_purifier_set_percentage_failed",
        )
        if (fixed := self._fixed_speed_characteristic("manualFan")) is not None:
            fixed.value = speed
        self._publish_write_update()
