"""Platform for climate integration."""

from typing import TYPE_CHECKING, Any, override

from boschshcpy import RoomClimateControlService, SHCClimateControl

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_BOOST,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC climate platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    async_add_entities(
        ClimateControl(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            room_name=session.room(device.room_id).name,
        )
        for device in session.device_helper.climate_controls
    )


class ClimateControl(SHCEntity, ClimateEntity):
    """Representation of a SHC room climate control."""

    _attr_name = None
    _attr_max_temp = 30.0
    _attr_min_temp = 5.0
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _device: SHCClimateControl

    def __init__(
        self,
        hass: HomeAssistant,
        device: SHCClimateControl,
        parent_id: str,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the room climate control."""
        super().__init__(
            hass=hass, device=device, parent_id=parent_id, entry_id=entry_id
        )
        if TYPE_CHECKING:
            assert self._attr_device_info is not None
        self._attr_device_info["name"] = room_name

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported features."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        if self.preset_modes:
            features |= ClimateEntityFeature.PRESET_MODE
        return features

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.temperature

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._device.setpoint_temperature

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if self._device.summer_mode:
            return HVACMode.OFF
        if self._device.supports_cooling and self._device.cooling_mode:
            return HVACMode.COOL
        if (
            self._device.operation_mode
            is RoomClimateControlService.OperationMode.AUTOMATIC
        ):
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the available HVAC modes."""
        modes = [HVACMode.AUTO, HVACMode.HEAT]
        if self._device.supports_cooling:
            modes.append(HVACMode.COOL)
        modes.append(HVACMode.OFF)
        return modes

    @property
    @override
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        hvac_mode = self.hvac_mode
        if hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if hvac_mode == HVACMode.COOL:
            return HVACAction.COOLING
        return HVACAction.HEATING if self._device.has_demand else HVACAction.IDLE

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the active override preset."""
        if self._device.supports_boost_mode and self._device.boost_mode:
            return PRESET_BOOST
        if self._device.supports_eco and self._device.low:
            return PRESET_ECO
        return None

    @property
    @override
    def preset_modes(self) -> list[str] | None:
        """Return the available override presets."""
        presets = []
        if self._device.supports_boost_mode:
            presets.append(PRESET_BOOST)
        if self._device.supports_eco:
            presets.append(PRESET_ECO)
        return presets or None

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self.set_hvac_mode(hvac_mode)
            if hvac_mode == HVACMode.OFF:
                return
        elif self.hvac_mode == HVACMode.OFF:
            return

        # The SHC rejects setpoint writes while the room is in eco.
        if self._device.low:
            self._device.low = False
        self._device.setpoint_temperature = kwargs[ATTR_TEMPERATURE]

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if self._device.low:
            self._device.low = False

        if hvac_mode == HVACMode.OFF:
            self._device.summer_mode = True
            return

        if self._device.summer_mode:
            self._device.summer_mode = False
        if hvac_mode == HVACMode.COOL:
            self._device.cooling_mode = True
            return

        if self._device.supports_cooling:
            self._device.cooling_mode = False
        self._device.operation_mode = (
            RoomClimateControlService.OperationMode.AUTOMATIC
            if hvac_mode == HVACMode.AUTO
            else RoomClimateControlService.OperationMode.MANUAL
        )

    @override
    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the override preset."""
        if preset_mode == PRESET_BOOST:
            self._device.boost_mode = True
            return

        if self._device.supports_boost_mode and self._device.boost_mode:
            self._device.boost_mode = False
        self._device.low = True

    @override
    def turn_on(self) -> None:
        """Turn the climate device on."""
        self.set_hvac_mode(HVACMode.AUTO)

    @override
    def turn_off(self) -> None:
        """Turn the climate device off."""
        self.set_hvac_mode(HVACMode.OFF)
