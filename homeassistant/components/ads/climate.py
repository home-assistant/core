"""Support for ADS climate control devices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ADS_TYPEMAP,
    CONF_ADS_FIELDS,
    CONF_ADS_HUB,
    CONF_ADS_HUB_DEFAULT,
    CONF_ADS_SYMBOLS,
    CONF_ADS_TEMPLATE,
    DOMAIN,
    STATE_KEY_CURRENT_TEMP,
    STATE_KEY_HVAC_MODE,
    STATE_KEY_TARGET_TEMP,
    AdsClimateKeys,
    AdsDiscoveryKeys,
    AdsType,
)
from .entity import AdsEntity
from .hub import AdsHub

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_HUB, default=CONF_ADS_HUB_DEFAULT): cv.string,
        vol.Required(AdsClimateKeys.VAR_CURRENT_TEMPERATURE): cv.string,
        vol.Required(AdsClimateKeys.VAR_TARGET_TEMPERATURE): cv.string,
        vol.Optional(AdsClimateKeys.FACTOR): vol.Coerce(int),
        vol.Optional(AdsClimateKeys.TYPE, default=AdsType.REAL): vol.All(
            vol.Coerce(AdsType),
            vol.In(
                [
                    AdsType.BYTE,
                    AdsType.INT,
                    AdsType.UINT,
                    AdsType.SINT,
                    AdsType.USINT,
                    AdsType.DINT,
                    AdsType.UDINT,
                    AdsType.WORD,
                    AdsType.DWORD,
                    AdsType.REAL,
                    AdsType.LREAL,
                ]
            ),
        ),
        vol.Optional(AdsClimateKeys.TYPE_MODE, default=AdsType.UINT): vol.All(
            vol.Coerce(AdsType),
            vol.In(
                [
                    AdsType.BYTE,
                    AdsType.INT,
                    AdsType.UINT,
                    AdsType.SINT,
                    AdsType.USINT,
                    AdsType.DINT,
                    AdsType.UDINT,
                    AdsType.WORD,
                    AdsType.DWORD,
                ]
            ),
        ),
        vol.Optional(AdsClimateKeys.VAR_HVAC_MODE): cv.string,
        vol.Optional(AdsClimateKeys.HVAC_MODES): vol.All(
            cv.ensure_list,
            [
                vol.In(
                    [
                        HVACMode.OFF,
                        HVACMode.HEAT,
                        HVACMode.COOL,
                        HVACMode.HEAT_COOL,
                        HVACMode.AUTO,
                        HVACMode.DRY,
                        HVACMode.FAN_ONLY,
                    ]
                )
            ],
        ),
        vol.Optional(AdsClimateKeys.VAL_MIN_TEMPERATURE, default=7.0): vol.Coerce(
            float
        ),
        vol.Optional(AdsClimateKeys.VAL_MAX_TEMPERATURE, default=35.0): vol.Coerce(
            float
        ),
        vol.Optional(
            AdsClimateKeys.UNIT_OF_MEASUREMENT, default=UnitOfTemperature.CELSIUS
        ): vol.In(
            [
                UnitOfTemperature.CELSIUS,
                UnitOfTemperature.FAHRENHEIT,
                UnitOfTemperature.KELVIN,
            ]
        ),
        vol.Optional(
            AdsClimateKeys.NAME, default=AdsClimateKeys.DEFAULT_NAME
        ): cv.string,
    }
)


def _map_hvac_mode(mode: int) -> HVACMode:
    """Map integer modes to HVACMode enums."""
    mapping = {
        1: HVACMode.OFF,
        2: HVACMode.COOL,
        4: HVACMode.HEAT,
        8: HVACMode.HEAT_COOL,
        16: HVACMode.AUTO,
        32: HVACMode.DRY,
        64: HVACMode.FAN_ONLY,
    }
    return mapping.get(mode, HVACMode.OFF)


def _hvac_mode_to_int(hvac_mode: HVACMode) -> int | None:
    """Map HVACMode enums to integer values."""
    mapping = {
        HVACMode.OFF: 1,
        HVACMode.COOL: 2,
        HVACMode.HEAT: 4,
        HVACMode.HEAT_COOL: 8,
        HVACMode.AUTO: 16,
        HVACMode.DRY: 32,
        HVACMode.FAN_ONLY: 64,
    }
    return mapping.get(hvac_mode)


def _hvac_modes_from_int(mode: int) -> list[HVACMode]:
    """Extract a list of HVACMode enums from the given mode bitmask."""
    valid_bitmasks = [1, 2, 4, 8, 16, 32, 64]
    hvac_modes = [
        _mode
        for bitmask in valid_bitmasks
        if mode & bitmask and (_mode := _map_hvac_mode(bitmask))
    ]
    return hvac_modes if hvac_modes else [HVACMode.OFF]


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Climate platform for ADS."""
    if discovery_info is not None:
        _hub_name = discovery_info.get(CONF_ADS_HUB)
        _hub_key = f"{DOMAIN}_{_hub_name}"
        _ads_hub = hass.data.get(_hub_key)
        if not _ads_hub:
            return

        _entities = []
        _symbols = discovery_info.get(CONF_ADS_SYMBOLS, [])
        _template = discovery_info.get(CONF_ADS_TEMPLATE, {})
        _fields = _template.get(CONF_ADS_FIELDS, {})

        for _symbol in _symbols:
            _path = _symbol.get(AdsDiscoveryKeys.ADSPATH)
            _name = _symbol.get(AdsDiscoveryKeys.NAME)
            _device_type = _symbol.get(AdsDiscoveryKeys.DEVICE_TYPE)
            if not _name or not _device_type:
                continue

            _ads_type = AdsType(_fields.get(AdsClimateKeys.TYPE))
            _ads_type_mode = AdsType(_fields.get(AdsClimateKeys.TYPE_MODE))
            _adsval_min_temperature = float(
                _fields.get(AdsClimateKeys.VAL_MIN_TEMPERATURE)
            )
            _adsval_max_temperature = float(
                _fields.get(AdsClimateKeys.VAL_MAX_TEMPERATURE)
            )
            _temperature_unit = UnitOfTemperature(
                _fields.get(AdsClimateKeys.UNIT_OF_MEASUREMENT)
            )
            _hvac_modes = _hvac_modes_from_int(_device_type)
            _factor: int | None = _fields.get(AdsClimateKeys.FACTOR)

            _ads_var_current_temperature = (
                _path + "." + _fields.get(AdsClimateKeys.VAR_CURRENT_TEMPERATURE)
            )
            _ads_var_target_temperature = (
                _path + "." + _fields.get(AdsClimateKeys.VAR_TARGET_TEMPERATURE)
            )
            _ads_var_hvac_mode = _path + "." + _fields.get(AdsClimateKeys.VAR_HVAC_MODE)

            _entities.append(
                AdsClimate(
                    ads_hub=_ads_hub,
                    name=_name,
                    ads_type=_ads_type,
                    ads_type_mode=_ads_type_mode,
                    factor=_factor,
                    ads_var_current_temperature=_ads_var_current_temperature,
                    ads_var_target_temperature=_ads_var_target_temperature,
                    ads_var_hvac_mode=_ads_var_hvac_mode,
                    hvac_modes=_hvac_modes,
                    adsval_min_temperature=_adsval_min_temperature,
                    adsval_max_temperature=_adsval_max_temperature,
                    temperature_unit=_temperature_unit,
                )
            )

        add_entities(_entities)
        return

    hub_name: str = config[CONF_ADS_HUB]
    hub_key = f"{DOMAIN}_{hub_name}"
    ads_hub = hass.data.get(hub_key)
    if not ads_hub:
        return

    name: str = config[AdsClimateKeys.NAME]
    ads_type: AdsType = config[AdsClimateKeys.TYPE]
    ads_type_mode: AdsType = config[AdsClimateKeys.TYPE_MODE]
    factor: int | None = config.get(AdsClimateKeys.FACTOR)
    hvac_modes = config.get(AdsClimateKeys.HVAC_MODES)
    adsval_min_temperature: float = config[AdsClimateKeys.VAL_MIN_TEMPERATURE]
    adsval_max_temperature: float = config[AdsClimateKeys.VAL_MAX_TEMPERATURE]
    temperature_unit: str = config[AdsClimateKeys.UNIT_OF_MEASUREMENT]

    ads_var_current_temperature: str = config[AdsClimateKeys.VAR_CURRENT_TEMPERATURE]
    ads_var_target_temperature: str = config[AdsClimateKeys.VAR_TARGET_TEMPERATURE]
    ads_var_hvac_mode: str | None = config.get(AdsClimateKeys.VAR_HVAC_MODE)

    add_entities(
        [
            AdsClimate(
                ads_hub=ads_hub,
                name=name,
                ads_type=ads_type,
                ads_type_mode=ads_type_mode,
                factor=factor,
                ads_var_current_temperature=ads_var_current_temperature,
                ads_var_target_temperature=ads_var_target_temperature,
                ads_var_hvac_mode=ads_var_hvac_mode,
                hvac_modes=hvac_modes,
                adsval_min_temperature=adsval_min_temperature,
                adsval_max_temperature=adsval_max_temperature,
                temperature_unit=temperature_unit,
            )
        ]
    )


class AdsClimate(AdsEntity, ClimateEntity):
    """Representation of ADS climate control."""

    def __init__(
        self,
        ads_hub: AdsHub,
        name: str,
        ads_type: AdsType,
        ads_type_mode: AdsType,
        factor: int | None,
        ads_var_current_temperature: str,
        ads_var_target_temperature: str | None,
        ads_var_hvac_mode: str | None,
        hvac_modes: list[HVACMode] | None = None,
        temperature_unit: str | None = None,
        adsval_min_temperature: float = 0.0,
        adsval_max_temperature: float = 0.0,
    ) -> None:
        """Initialize AdsClimate entity."""
        super().__init__(ads_hub, name, ads_var_current_temperature)

        self._ads_type = ads_type
        self._ads_type_mode = ads_type_mode
        self._factor = factor
        self._ads_var_current_temperature = ads_var_current_temperature
        self._ads_var_target_temperature = ads_var_target_temperature
        self._ads_var_hvac_mode = ads_var_hvac_mode

        self._state_dict[STATE_KEY_CURRENT_TEMP] = None
        self._state_dict[STATE_KEY_TARGET_TEMP] = None
        self._state_dict[STATE_KEY_HVAC_MODE] = None

        self._attr_min_temp = adsval_min_temperature
        self._attr_max_temp = adsval_max_temperature
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        self._attr_hvac_modes = hvac_modes if hvac_modes is not None else []
        self._attr_temperature_unit = (
            UnitOfTemperature(temperature_unit)
            if temperature_unit is not None
            else UnitOfTemperature.CELSIUS
        )

    async def async_added_to_hass(self) -> None:
        """Register device notification."""

        if self._ads_var_current_temperature is not None:
            await self.async_initialize_device(
                self._ads_var_current_temperature,
                ADS_TYPEMAP[self._ads_type],
                STATE_KEY_CURRENT_TEMP,
                self._factor,
            )

        if self._ads_var_target_temperature is not None:
            await self.async_initialize_device(
                self._ads_var_target_temperature,
                ADS_TYPEMAP[self._ads_type],
                STATE_KEY_TARGET_TEMP,
                self._factor,
            )

        if self._ads_var_hvac_mode is not None:
            await self.async_initialize_device(
                self._ads_var_hvac_mode,
                ADS_TYPEMAP[self._ads_type_mode],
                STATE_KEY_HVAC_MODE,
            )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._state_dict[STATE_KEY_CURRENT_TEMP]

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._state_dict[STATE_KEY_TARGET_TEMP]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current operation mode."""
        return _map_hvac_mode(self._state_dict[STATE_KEY_HVAC_MODE])

    @property
    def temperature_unit(self) -> str:
        """Return the configured or default display unit for temperature."""
        return self._attr_temperature_unit

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._attr_min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._attr_max_temp

    @property
    def available_hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        return self._attr_hvac_modes

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None and self._ads_var_target_temperature is not None:
            if self._factor is not None:
                temperature *= self._factor
            self._ads_hub.write_by_name(
                self._ads_var_target_temperature,
                temperature,
                ADS_TYPEMAP[self._ads_type],
            )

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        mode = _hvac_mode_to_int(hvac_mode)
        if mode is not None and self._ads_var_hvac_mode is not None:
            self._ads_hub.write_by_name(
                self._ads_var_hvac_mode, mode, ADS_TYPEMAP[self._ads_type_mode]
            )
