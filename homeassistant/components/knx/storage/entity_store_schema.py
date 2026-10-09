"""KNX entity store schema."""

from collections.abc import Hashable
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Annotated, Any

import probatio
from probatio import Key
from xknx.dpt import DPTBase, DPTBinary, DPTNumeric
from xknx.exceptions import ConversionError

from homeassistant.components.climate import HVACMode
from homeassistant.components.number import (
    DEVICE_CLASS_UNITS as NUMBER_DEVICE_CLASS_UNITS,
    NumberMode,
)
from homeassistant.components.sensor import (
    DEVICE_CLASS_UNITS as SENSOR_DEVICE_CLASS_UNITS,
    SensorDeviceClass,
)
from homeassistant.components.text import TextMode
from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_ENTITY_ID,
    CONF_PAYLOAD,
    CONF_PLATFORM,
    EntityCategory,
    Platform,
)
from homeassistant.helpers import selector
from homeassistant.helpers.typing import VolDictType

from ..const import (
    CONF_PAYLOAD_LENGTH,
    CONF_RESPOND_TO_READ,
    CONF_SYNC_STATE,
    CONF_VALUE,
    DOMAIN,
    SUPPORTED_PLATFORMS_UI,
    ColorTempModes,
    FanZeroMode,
    SelectConf,
)
from ..dpt import get_supported_dpts, raw_payload_length
from ..validation import (
    entity_category_supported,
    parse_entity_category,
    validate_number_attributes,
    validate_sensor_attributes,
)
from .const import CONF_DATA, CONF_DPT, CONF_ENTITY, CONF_GA_SEND
from .knx_selector import (
    AllSerializeFirst,
    GASelector,
    GroupAddressConfig,
    GroupSelect,
    GroupSelectOption,
    KnxPayloadSelector,
    KNXSectionFlat,
    KnxSelectOptionsSelector,
    SyncStateSelector,
    ga,
    group_select,
)

SyncState = Annotated[bool | str | int, SyncStateSelector()]
SyncStateAllowFalse = Annotated[bool | str | int, SyncStateSelector(allow_false=True)]


@dataclass(kw_only=True, slots=True)
class BaseEntityConfig:
    """Common UI configuration of a KNX entity."""

    name: str | None = None
    device_info: str | None = None
    entity_category: Annotated[
        EntityCategory | None, probatio.Coerce(parse_entity_category)
    ] = None

    @property
    def xknx_name(self) -> str:
        """Name of the xknx device, empty when HA names the entity after its device."""
        return self.name or ""


def _name_or_device_required(config: BaseEntityConfig) -> BaseEntityConfig:
    """Require a name, unless the entity is named after its device."""
    if not config.name and config.device_info is None:
        raise probatio.AnyInvalid("One of `Device` or `Name` is required")
    return config


def base_entity_schema(platform: Platform) -> probatio.All:
    """Return the base entity schema for a platform."""
    return probatio.All(
        probatio.DataclassSchema(
            BaseEntityConfig,
            {CONF_ENTITY_CATEGORY: entity_category_supported(platform)},
        ),
        _name_or_device_required,
    )


@dataclass(kw_only=True, slots=True)
class KnxEntityData[KnxT]:
    """Validated UI entity data: the common `entity` and the platform `knx` part."""

    entity: BaseEntityConfig
    knx: KnxT


def _to_entity_data(data: dict[str, Any]) -> KnxEntityData[Any]:
    return KnxEntityData(entity=data[CONF_ENTITY], knx=data[DOMAIN])


@dataclass(kw_only=True, slots=True)
class BinarySensorKnxConfig:
    """UI configuration of a KNX binary sensor."""

    ga_sensor: Annotated[
        GroupAddressConfig, ga(write=False, state_required=True, valid_dpt="1")
    ]
    invert: Annotated[bool, selector.BooleanSelector()] = False
    section_advanced_options: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ignore_internal_state: Annotated[bool, selector.BooleanSelector()] = False
    context_timeout: Annotated[
        float | None,
        probatio.Maybe(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=10, step=0.1, unit_of_measurement="s"
                )
            )
        ),
    ] = None
    reset_after: Annotated[
        float | None,
        probatio.Maybe(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=600, step=0.1, unit_of_measurement="s"
                )
            )
        ),
    ] = None
    sync_state: Annotated[SyncStateAllowFalse, Key(required=True)] = True


BINARY_SENSOR_KNX_SCHEMA = probatio.DataclassSchema(BinarySensorKnxConfig)


def _button_data_sub_validator(config: dict) -> dict:
    """Validate data matching configured DPT."""
    dpt = config[CONF_GA_SEND].get(CONF_DPT)
    transcoder = None
    if dpt:
        transcoder = DPTBase.parse_transcoder(dpt)
        assert transcoder is not None  # already checked by GASelector

        if CONF_VALUE in config[CONF_DATA]:
            try:
                transcoder.to_knx(config[CONF_DATA][CONF_VALUE])
            except ConversionError as ex:
                raise probatio.Invalid(
                    f"Value invalid for DPT {transcoder.dpt_number_str()}",
                    path=([CONF_DATA]),
                ) from ex
        elif CONF_PAYLOAD_LENGTH in config[CONF_DATA]:
            length = config[CONF_DATA][CONF_PAYLOAD_LENGTH]
            if length != transcoder.payload_length or (
                length != 0 and transcoder.payload_type is DPTBinary
            ):
                raise probatio.Invalid(
                    f"Payload length invalid for DPT {transcoder.dpt_number_str()}",
                    path=([CONF_DATA]),
                )
        return config
    # without DPT only raw allowed -> payload + payload_length (checked by KnxPayloadSelector)
    if CONF_PAYLOAD_LENGTH in config[CONF_DATA]:
        return config
    raise probatio.Invalid("Invalid configuration for button entity")


BUTTON_KNX_SCHEMA = AllSerializeFirst(
    probatio.Schema(
        {
            probatio.Required(CONF_GA_SEND): GASelector(
                state=False,
                write_required=True,
                passive=False,
                dpt=["numeric", "enum", "complex", "string"],
                dpt_required=False,  # for raw payload support
            ),
            probatio.Required(CONF_DATA): KnxPayloadSelector(ga_path=CONF_GA_SEND),
        },
    ),
    _button_data_sub_validator,
)

_TRAVELLING_TIME_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(min=0, max=1000, step=0.1, unit_of_measurement="s")
)


@dataclass(kw_only=True, slots=True)
class CoverKnxConfig:
    """UI configuration of a KNX cover."""

    ga_up_down: Annotated[GroupAddressConfig | None, ga(state=False, valid_dpt="1")] = (
        None
    )
    invert_updown: Annotated[bool, selector.BooleanSelector()] = False
    ga_stop: Annotated[GroupAddressConfig | None, ga(state=False, valid_dpt="1")] = None
    ga_step: Annotated[GroupAddressConfig | None, ga(state=False, valid_dpt="1")] = None
    section_position_control: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_position_set: Annotated[
        GroupAddressConfig | None, ga(state=False, valid_dpt="5.001")
    ] = None
    ga_position_state: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="5.001")
    ] = None
    invert_position: Annotated[bool, selector.BooleanSelector()] = False
    section_tilt_control: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_angle: Annotated[GroupAddressConfig | None, ga(valid_dpt="5.001")] = None
    invert_angle: Annotated[bool, selector.BooleanSelector()] = False
    section_travel_time: Annotated[None, Key(remove=True), KNXSectionFlat()] = None
    travelling_time_up: Annotated[
        float, Key(required=True), _TRAVELLING_TIME_SELECTOR
    ] = 25
    travelling_time_down: Annotated[
        float, Key(required=True), _TRAVELLING_TIME_SELECTOR
    ] = 25
    sync_state: SyncState = True


def _cover_control_sub_validator(config: CoverKnxConfig) -> CoverKnxConfig:
    """Require a way to move the cover."""
    if not any(
        ga_config is not None and ga_config.write is not None
        for ga_config in (config.ga_up_down, config.ga_position_set)
    ):
        raise probatio.Invalid(
            "At least one of 'Open/Close control' or"
            " 'Position - Set position' is required."
        )
    return config


COVER_KNX_SCHEMA = AllSerializeFirst(
    probatio.DataclassSchema(CoverKnxConfig, extra=probatio.REMOVE_EXTRA),
    _cover_control_sub_validator,
)


@dataclass(kw_only=True, slots=True)
class DateKnxConfig:
    """UI configuration of a KNX date entity."""

    ga_date: Annotated[GroupAddressConfig, ga(write_required=True, valid_dpt="11.001")]
    respond_to_read: Annotated[bool, selector.BooleanSelector()] = False
    sync_state: SyncState = True


DATE_KNX_SCHEMA = probatio.DataclassSchema(DateKnxConfig)


@dataclass(kw_only=True, slots=True)
class DatetimeKnxConfig:
    """UI configuration of a KNX datetime entity."""

    ga_datetime: Annotated[
        GroupAddressConfig, ga(write_required=True, valid_dpt="19.001")
    ]
    respond_to_read: Annotated[bool, selector.BooleanSelector()] = False
    sync_state: SyncState = True


DATETIME_KNX_SCHEMA = probatio.DataclassSchema(DatetimeKnxConfig)


@dataclass(kw_only=True, slots=True)
class FanSpeedPercentage:
    """Fan speed controlled in percent."""

    ga_speed: Annotated[GroupAddressConfig, ga(write_required=True, valid_dpt="5.001")]


@dataclass(kw_only=True, slots=True)
class FanSpeedStep:
    """Fan speed controlled in steps."""

    ga_step: Annotated[GroupAddressConfig, ga(write_required=True, valid_dpt="5.010")]
    max_step: Annotated[
        int,
        Key(required=True),
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=100, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        probatio.Coerce(int),
    ] = 3


@dataclass(kw_only=True, slots=True)
class FanKnxConfig:
    """UI configuration of a KNX fan."""

    ga_switch: Annotated[
        GroupAddressConfig | None, ga(write_required=True, valid_dpt="1")
    ] = None
    speed: Annotated[
        FanSpeedPercentage | FanSpeedStep | None,
        group_select(
            ("percentage_mode", FanSpeedPercentage),
            ("step_mode", FanSpeedStep),
            collapsible=False,
        ),
    ] = None
    ga_oscillation: Annotated[
        GroupAddressConfig | None, ga(write_required=True, valid_dpt="1")
    ] = None
    sync_state: SyncState = True


def _fan_switch_or_speed_required(config: FanKnxConfig) -> FanKnxConfig:
    """Require a switch or a speed address."""
    if config.ga_switch is None and config.speed is None:
        raise probatio.AnyInvalid(
            "At least one of 'Switch' or 'Fan speed' is required."
        )
    return config


FAN_KNX_SCHEMA = AllSerializeFirst(
    probatio.DataclassSchema(FanKnxConfig), _fan_switch_or_speed_required
)


@unique
class LightColorMode(StrEnum):
    """Enum for light color mode."""

    RGB = "232.600"
    RGBW = "251.600"
    XYY = "242.600"


_hs_color_inclusion_msg = (
    "'Hue', 'Saturation' and 'Brightness' addresses are required for HSV configuration"
)


@dataclass(kw_only=True, slots=True)
class LightColorSingleAddress:
    """Light color controlled by a single group address."""

    ga_color: Annotated[
        GroupAddressConfig | None, ga(write_required=True, dpt=LightColorMode)
    ] = None


@dataclass(kw_only=True, slots=True)
class LightColorIndividualAddresses:
    """Light color controlled by individual addresses per color channel."""

    ga_red_switch: Annotated[
        GroupAddressConfig | None, ga(write_required=False, valid_dpt="1")
    ] = None
    ga_red_brightness: Annotated[
        GroupAddressConfig, ga(write_required=True, valid_dpt="5.001")
    ]
    ga_green_switch: Annotated[
        GroupAddressConfig | None, ga(write_required=False, valid_dpt="1")
    ] = None
    ga_green_brightness: Annotated[
        GroupAddressConfig, ga(write_required=True, valid_dpt="5.001")
    ]
    ga_blue_switch: Annotated[
        GroupAddressConfig | None, ga(write_required=False, valid_dpt="1")
    ] = None
    ga_blue_brightness: Annotated[
        GroupAddressConfig, ga(write_required=True, valid_dpt="5.001")
    ]
    ga_white_switch: Annotated[
        GroupAddressConfig | None, ga(write_required=False, valid_dpt="1")
    ] = None
    ga_white_brightness: Annotated[
        GroupAddressConfig | None, ga(write_required=True, valid_dpt="5.001")
    ] = None


@dataclass(kw_only=True, slots=True)
class LightColorHsvAddresses:
    """Light color controlled by hue and saturation addresses."""

    ga_hue: Annotated[GroupAddressConfig, ga(write_required=True, valid_dpt="5.003")]
    ga_saturation: Annotated[
        GroupAddressConfig, ga(write_required=True, valid_dpt="5.001")
    ]


type LightColor = (
    LightColorSingleAddress | LightColorIndividualAddresses | LightColorHsvAddresses
)


@dataclass(kw_only=True, slots=True)
class LightKnxConfig:
    """UI configuration of a KNX light."""

    ga_switch: Annotated[
        GroupAddressConfig | None, ga(write_required=True, valid_dpt="1")
    ] = None
    ga_brightness: Annotated[
        GroupAddressConfig | None, ga(write_required=True, valid_dpt="5.001")
    ] = None
    section_color_temp: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_color_temp: Annotated[
        GroupAddressConfig | None, ga(write_required=True, dpt=ColorTempModes)
    ] = None
    color_temp_min: Annotated[
        int,
        Key(required=True),
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=10000, step=1, unit_of_measurement="K"
            )
        ),
        probatio.Coerce(int),
    ] = 2700
    color_temp_max: Annotated[
        int,
        Key(required=True),
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=10000, step=1, unit_of_measurement="K"
            )
        ),
        probatio.Coerce(int),
    ] = 6000
    color: Annotated[
        LightColor | None,
        group_select(
            ("single_address", LightColorSingleAddress),
            ("individual_addresses", LightColorIndividualAddresses),
            ("hsv_addresses", LightColorHsvAddresses),
        ),
    ] = None
    sync_state: SyncState = True


def _light_control_required(config: LightKnxConfig) -> LightKnxConfig:
    """Require a switch or individual color addresses, and brightness for HSV."""
    if config.ga_switch is None and not isinstance(
        config.color, LightColorIndividualAddresses
    ):
        raise probatio.AnyInvalid("either 'address' or 'individual_colors' is required")
    if (
        isinstance(config.color, LightColorHsvAddresses)
        and config.ga_brightness is None
    ):
        raise probatio.AnyInvalid(_hs_color_inclusion_msg)
    return config


LIGHT_KNX_SCHEMA = AllSerializeFirst(
    probatio.DataclassSchema(LightKnxConfig), _light_control_required
)


@dataclass(kw_only=True, slots=True)
class NotifyKnxConfig:
    """UI configuration of a KNX notify entity."""

    ga_send: Annotated[
        GroupAddressConfig,
        ga(state=False, passive=False, write_required=True, dpt=["string"]),
    ]


NOTIFY_KNX_SCHEMA = probatio.DataclassSchema(NotifyKnxConfig)


@dataclass(kw_only=True, slots=True)
class NumberKnxConfig:
    """UI configuration of a KNX number entity."""

    ga_sensor: Annotated[GroupAddressConfig, ga(write_required=True, dpt=["numeric"])]
    respond_to_read: Annotated[bool, selector.BooleanSelector()] = False
    section_advanced_options: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    mode: Annotated[
        str,
        Key(required=True),
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(NumberMode),
                translation_key="component.knx.config_panel.entities.create.number.knx.mode",
            ),
        ),
    ] = NumberMode.AUTO
    min: Annotated[float | None, probatio.Maybe(selector.NumberSelector())] = None
    max: Annotated[float | None, probatio.Maybe(selector.NumberSelector())] = None
    step: Annotated[
        float | None,
        probatio.Maybe(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, step="any", mode=selector.NumberSelectorMode.BOX
                )
            )
        ),
    ] = None
    unit_of_measurement: Annotated[
        str | None,
        probatio.Maybe(
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sorted(
                        {
                            str(unit)
                            for units in NUMBER_DEVICE_CLASS_UNITS.values()
                            for unit in units
                            if unit is not None
                        }
                    ),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                ),
            )
        ),
    ] = None
    device_class: Annotated[
        str | None,
        probatio.Maybe(
            selector.DeviceClassSelector(
                selector.DeviceClassSelectorConfig(domain=Platform.NUMBER)
            )
        ),
    ] = None
    sync_state: SyncState = True


def _number_limit_sub_validator(config: NumberKnxConfig) -> NumberKnxConfig:
    """Validate min, max, and step values for a number entity."""
    assert config.ga_sensor.dpt is not None  # required by the selector
    transcoder = DPTNumeric.parse_transcoder(config.ga_sensor.dpt)
    assert transcoder is not None  # already checked by GASelector
    validate_number_attributes(
        transcoder,
        min_config=config.min,
        max_config=config.max,
        step_config=config.step,
        device_class=config.device_class,
        unit_of_measurement=config.unit_of_measurement,
    )
    return config


NUMBER_KNX_SCHEMA = AllSerializeFirst(
    probatio.DataclassSchema(NumberKnxConfig),
    _number_limit_sub_validator,
)


@dataclass(kw_only=True, slots=True)
class SceneKnxConfig:
    """UI configuration of a KNX scene."""

    ga_scene: Annotated[
        GroupAddressConfig,
        ga(
            state=False,
            passive=False,
            write_required=True,
            valid_dpt=["17.001", "18.001"],
        ),
    ]
    scene_number: Annotated[
        int,
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=64, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        probatio.Coerce(int),
    ]


SCENE_KNX_SCHEMA = probatio.DataclassSchema(SceneKnxConfig)


def _select_options_sub_validator(config: dict) -> dict:
    """Validate select options against the configured DPT.

    The `options_source` group selects one of two modes, distinguished by the
    group address key:
    - `ga_enum`: options are derived from a required enum DPT.
    - `ga_custom`: options are configured manually, each as a typed value (needs
      a DPT) or a raw payload. Payload ranges are validated per option by the
      options selector.

    All options are sent to the same group address, so they have to share a
    single payload length - taken from the DPT if one is configured.
    """
    source = config[SelectConf.OPTIONS_SOURCE]
    if SelectConf.GA_ENUM in source:
        dpt = source[SelectConf.GA_ENUM].get(CONF_DPT)
        if dpt is None or get_supported_dpts()[dpt]["dpt_class"] != "enum":
            raise probatio.Invalid(
                "An enum data point type is required",
                path=[SelectConf.OPTIONS_SOURCE, SelectConf.GA_ENUM],
            )
        return config

    error_path: list[Hashable] = [SelectConf.OPTIONS_SOURCE, SelectConf.CUSTOM_OPTIONS]
    options = source[SelectConf.CUSTOM_OPTIONS]
    if not options:
        raise probatio.Invalid("At least one option is required", path=error_path)

    dpt = source[SelectConf.GA_CUSTOM].get(CONF_DPT)
    transcoder = DPTBase.parse_transcoder(dpt) if dpt is not None else None
    payload_length = raw_payload_length(transcoder) if transcoder is not None else None

    options_seen: set[str] = set()
    payloads_seen: set[int] = set()
    for option in options:
        name = option[SelectConf.OPTION]
        if name in options_seen:
            raise probatio.Invalid(
                f"Duplicate option not allowed: {name}", path=error_path
            )
        options_seen.add(name)

        if CONF_VALUE in option:
            if transcoder is None:
                raise probatio.Invalid(
                    f"A data point type is required for typed option '{name}'",
                    path=error_path,
                )
            try:
                payload = int.from_bytes(
                    transcoder.validate_payload(transcoder.to_knx(option[CONF_VALUE])),
                    byteorder="big",
                )
            except ConversionError as ex:
                raise probatio.Invalid(
                    f"Value invalid for option '{name}' with DPT "
                    f"{transcoder.dpt_number_str()}",
                    path=error_path,
                ) from ex
        else:
            option_length = option[CONF_PAYLOAD_LENGTH]
            if payload_length is None:
                payload_length = option_length
            elif option_length != payload_length:
                expected = (
                    f"DPT {transcoder.dpt_number_str()}"
                    if transcoder is not None
                    else "the other options"
                )
                raise probatio.Invalid(
                    f"Payload length {option_length} of option '{name}' doesn't "
                    f"match payload length {payload_length} of {expected}",
                    path=error_path,
                )
            payload = int(option[CONF_PAYLOAD], 16)

        if payload in payloads_seen:
            raise probatio.Invalid(
                f"Duplicate payload not allowed for option '{name}'", path=error_path
            )
        payloads_seen.add(payload)
    return config


SELECT_KNX_SCHEMA = AllSerializeFirst(
    probatio.Schema(
        {
            probatio.Required(SelectConf.OPTIONS_SOURCE): GroupSelect(
                GroupSelectOption(
                    translation_key="from_dpt",
                    schema={
                        probatio.Required(SelectConf.GA_ENUM): GASelector(
                            write_required=True, dpt=["enum"]
                        ),
                    },
                ),
                GroupSelectOption(
                    translation_key="custom",
                    schema={
                        probatio.Required(SelectConf.GA_CUSTOM): GASelector(
                            write_required=True,
                            dpt=["numeric", "enum", "complex", "string"],
                            dpt_required=False,
                        ),
                        probatio.Required(
                            SelectConf.CUSTOM_OPTIONS
                        ): KnxSelectOptionsSelector(ga_path=SelectConf.GA_CUSTOM),
                    },
                ),
                collapsible=False,
            ),
            probatio.Optional(
                CONF_RESPOND_TO_READ, default=False
            ): selector.BooleanSelector(),
            probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        }
    ),
    _select_options_sub_validator,
)


@dataclass(kw_only=True, slots=True)
class SwitchKnxConfig:
    """UI configuration of a KNX switch."""

    ga_switch: Annotated[GroupAddressConfig, ga(write_required=True, valid_dpt="1")]
    invert: Annotated[bool, selector.BooleanSelector()] = False
    respond_to_read: Annotated[bool, selector.BooleanSelector()] = False
    sync_state: SyncState = True


SWITCH_KNX_SCHEMA = probatio.DataclassSchema(SwitchKnxConfig)


@dataclass(kw_only=True, slots=True)
class TextKnxConfig:
    """UI configuration of a KNX text entity."""

    ga_text: Annotated[GroupAddressConfig, ga(write_required=True, dpt=["string"])]
    mode: Annotated[
        str,
        Key(required=True),
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(TextMode),
                translation_key="component.knx.config_panel.entities.create.text.knx.mode",
            ),
        ),
    ] = TextMode.TEXT
    respond_to_read: Annotated[bool, selector.BooleanSelector()] = False
    sync_state: SyncState = True


TEXT_KNX_SCHEMA = probatio.DataclassSchema(TextKnxConfig)


@dataclass(kw_only=True, slots=True)
class TimeKnxConfig:
    """UI configuration of a KNX time entity."""

    ga_time: Annotated[GroupAddressConfig, ga(write_required=True, valid_dpt="10.001")]
    respond_to_read: Annotated[bool, selector.BooleanSelector()] = False
    sync_state: SyncState = True


TIME_KNX_SCHEMA = probatio.DataclassSchema(TimeKnxConfig)


@unique
class ConfSetpointShiftMode(StrEnum):
    """Enum for setpoint shift mode."""

    COUNT = "6.010"
    FLOAT = "9.002"


@unique
class ConfClimateFanSpeedMode(StrEnum):
    """Enum for climate fan speed mode."""

    PERCENTAGE = "5.001"
    STEPS = "5.010"


_TEMPERATURE_STEP_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(min=0.1, max=2, step=0.1, unit_of_measurement="K")
)


@dataclass(kw_only=True, slots=True)
class ClimateTargetTemperature:
    """Target temperature set directly."""

    ga_temperature_target: Annotated[
        GroupAddressConfig, ga(write_required=True, valid_dpt="9.001")
    ]
    min_temp: Annotated[
        float,
        Key(required=True),
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=-20, max=80, step=1, unit_of_measurement="°C"
            )
        ),
    ] = 7
    max_temp: Annotated[
        float,
        Key(required=True),
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, unit_of_measurement="°C"
            )
        ),
    ] = 28
    temperature_step: Annotated[
        float, Key(required=True), _TEMPERATURE_STEP_SELECTOR
    ] = 0.1


@dataclass(kw_only=True, slots=True)
class ClimateSetpointShift:
    """Target temperature set by shifting a base setpoint."""

    ga_temperature_target: Annotated[
        GroupAddressConfig, ga(write=False, state_required=True, valid_dpt="9.001")
    ]
    ga_setpoint_shift: Annotated[
        GroupAddressConfig,
        ga(write_required=True, state_required=True, dpt=ConfSetpointShiftMode),
    ]
    setpoint_shift_min: Annotated[
        float,
        Key(required=True),
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=-32, max=0, step=1, unit_of_measurement="K"
            )
        ),
    ] = -6
    setpoint_shift_max: Annotated[
        float,
        Key(required=True),
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=32, step=1, unit_of_measurement="K"
            )
        ),
    ] = 6
    temperature_step: Annotated[
        float, Key(required=True), _TEMPERATURE_STEP_SELECTOR
    ] = 0.1


@dataclass(kw_only=True, slots=True)
class ClimateKnxConfig:
    """UI configuration of a KNX climate entity."""

    ga_temperature_current: Annotated[
        GroupAddressConfig, ga(write=False, state_required=True, valid_dpt="9.001")
    ]
    ga_humidity_current: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="9.007")
    ] = None
    target_temperature: Annotated[
        ClimateTargetTemperature | ClimateSetpointShift,
        group_select(
            ("group_direct_temp", ClimateTargetTemperature),
            ("group_setpoint_shift", ClimateSetpointShift),
            collapsible=False,
        ),
    ]
    section_activity: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_active: Annotated[GroupAddressConfig | None, ga(write=False, valid_dpt="1")] = (
        None
    )
    ga_valve: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="5.001")
    ] = None
    section_operation_mode: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_operation_mode: Annotated[GroupAddressConfig | None, ga(valid_dpt="20.102")] = (
        None
    )
    ignore_auto_mode: Annotated[bool, selector.BooleanSelector()] = False
    section_operation_mode_individual: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_operation_mode_comfort: Annotated[
        GroupAddressConfig | None, ga(state=False, valid_dpt="1")
    ] = None
    ga_operation_mode_economy: Annotated[
        GroupAddressConfig | None, ga(state=False, valid_dpt="1")
    ] = None
    ga_operation_mode_standby: Annotated[
        GroupAddressConfig | None, ga(state=False, valid_dpt="1")
    ] = None
    ga_operation_mode_protection: Annotated[
        GroupAddressConfig | None, ga(state=False, valid_dpt="1")
    ] = None
    section_heat_cool: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_heat_cool: Annotated[GroupAddressConfig | None, ga(valid_dpt="1.100")] = None
    section_on_off: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_on_off: Annotated[GroupAddressConfig | None, ga(valid_dpt="1")] = None
    on_off_invert: Annotated[bool, selector.BooleanSelector()] = False
    section_controller_mode: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_controller_mode: Annotated[GroupAddressConfig | None, ga(valid_dpt="20.105")] = (
        None
    )
    ga_controller_status: Annotated[GroupAddressConfig | None, ga(write=False)] = None
    default_controller_mode: Annotated[
        str,
        Key(required=True),
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(HVACMode),
                translation_key="component.climate.selector.hvac_mode",
            )
        ),
    ] = HVACMode.HEAT
    section_fan: Annotated[None, Key(remove=True), KNXSectionFlat(collapsible=True)] = (
        None
    )
    ga_fan_speed: Annotated[
        GroupAddressConfig | None, ga(dpt=ConfClimateFanSpeedMode)
    ] = None
    fan_max_step: Annotated[
        int,
        Key(required=True),
        selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=100, step=1)),
        probatio.Coerce(int),
    ] = 3
    fan_zero_mode: Annotated[
        str,
        Key(required=True),
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(FanZeroMode),
                translation_key="component.knx.config_panel.entities.create.climate.knx.fan_zero_mode",
            )
        ),
    ] = FanZeroMode.OFF
    ga_fan_swing: Annotated[GroupAddressConfig | None, ga(valid_dpt="1")] = None
    ga_fan_swing_horizontal: Annotated[GroupAddressConfig | None, ga(valid_dpt="1")] = (
        None
    )
    sync_state: SyncState = True


CLIMATE_KNX_SCHEMA = probatio.DataclassSchema(ClimateKnxConfig)


@dataclass(kw_only=True, slots=True)
class SensorKnxConfig:
    """UI configuration of a KNX sensor."""

    ga_sensor: Annotated[
        GroupAddressConfig,
        ga(write=False, state_required=True, dpt=["numeric", "string"]),
    ]
    section_advanced_options: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    unit_of_measurement: Annotated[
        str | None,
        probatio.Maybe(
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sorted(
                        {
                            str(unit)
                            for units in SENSOR_DEVICE_CLASS_UNITS.values()
                            for unit in units
                            if unit is not None
                        }
                    ),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="component.knx.selector.sensor_unit_of_measurement",
                    custom_value=True,
                ),
            )
        ),
    ] = None
    device_class: Annotated[
        str | None,
        probatio.Maybe(
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        cls.value
                        for cls in SensorDeviceClass
                        if cls != SensorDeviceClass.ENUM
                    ],
                    translation_key="component.knx.selector.sensor_device_class",
                    sort=True,
                )
            )
        ),
    ] = None
    state_class: Annotated[
        str | None, probatio.Maybe(selector.StateClassSelector())
    ] = None
    always_callback: Annotated[bool, selector.BooleanSelector()] = False
    sync_state: Annotated[SyncStateAllowFalse, Key(required=True)] = True


def _sensor_attribute_sub_validator(config: SensorKnxConfig) -> SensorKnxConfig:
    """Validate state_class, device_class and unit compatibility."""
    assert config.ga_sensor.dpt is not None  # required by the selector
    validate_sensor_attributes(
        get_supported_dpts()[config.ga_sensor.dpt],
        state_class=config.state_class,
        device_class=config.device_class,
        unit_of_measurement=config.unit_of_measurement,
    )
    return config


SENSOR_KNX_SCHEMA = AllSerializeFirst(
    probatio.DataclassSchema(SensorKnxConfig),
    _sensor_attribute_sub_validator,
)


@dataclass(kw_only=True, slots=True)
class WeatherKnxConfig:
    """UI configuration of a KNX weather entity."""

    ga_temperature: Annotated[
        GroupAddressConfig, ga(write=False, state_required=True, valid_dpt="9.001")
    ]
    ga_humidity: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="9.007")
    ] = None
    ga_air_pressure: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt=["9.006", "14.058"])
    ] = None
    ga_wind_speed: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="9.005")
    ] = None
    ga_wind_bearing: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="5.003")
    ] = None
    section_brightness: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_brightness_east: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="9.004")
    ] = None
    ga_brightness_south: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="9.004")
    ] = None
    ga_brightness_west: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="9.004")
    ] = None
    ga_brightness_north: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="9.004")
    ] = None
    section_day_night: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_day_night: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="1.024")
    ] = None
    invert_day_night: Annotated[bool, selector.BooleanSelector()] = False
    section_alarms: Annotated[
        None, Key(remove=True), KNXSectionFlat(collapsible=True)
    ] = None
    ga_rain_alarm: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="1")
    ] = None
    ga_frost_alarm: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="1")
    ] = None
    ga_wind_alarm: Annotated[
        GroupAddressConfig | None, ga(write=False, valid_dpt="1")
    ] = None
    sync_state: SyncState = True


WEATHER_KNX_SCHEMA = probatio.DataclassSchema(WeatherKnxConfig)

KNX_SCHEMA_FOR_PLATFORM = {
    Platform.BINARY_SENSOR: BINARY_SENSOR_KNX_SCHEMA,
    Platform.BUTTON: BUTTON_KNX_SCHEMA,
    Platform.CLIMATE: CLIMATE_KNX_SCHEMA,
    Platform.COVER: COVER_KNX_SCHEMA,
    Platform.DATE: DATE_KNX_SCHEMA,
    Platform.DATETIME: DATETIME_KNX_SCHEMA,
    Platform.FAN: FAN_KNX_SCHEMA,
    Platform.LIGHT: LIGHT_KNX_SCHEMA,
    Platform.NOTIFY: NOTIFY_KNX_SCHEMA,
    Platform.NUMBER: NUMBER_KNX_SCHEMA,
    Platform.SCENE: SCENE_KNX_SCHEMA,
    Platform.SELECT: SELECT_KNX_SCHEMA,
    Platform.SENSOR: SENSOR_KNX_SCHEMA,
    Platform.SWITCH: SWITCH_KNX_SCHEMA,
    Platform.TEXT: TEXT_KNX_SCHEMA,
    Platform.TIME: TIME_KNX_SCHEMA,
    Platform.WEATHER: WEATHER_KNX_SCHEMA,
}

ENTITY_STORE_DATA_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Required(CONF_PLATFORM): probatio.All(
                probatio.Coerce(Platform),
                probatio.In(SUPPORTED_PLATFORMS_UI),
            ),
            probatio.Required(CONF_DATA): dict,
        },
        extra=probatio.ALLOW_EXTRA,
    ),
    probatio.TaggedUnion(
        CONF_PLATFORM,
        {
            platform: probatio.Schema(
                {
                    probatio.Required(CONF_DATA): probatio.All(
                        probatio.Schema(
                            {
                                probatio.Required(CONF_ENTITY): base_entity_schema(
                                    platform
                                ),
                                probatio.Required(DOMAIN): knx_schema,
                            },
                            extra=probatio.PREVENT_EXTRA,  # restrict in data key for yaml edit
                        ),
                        _to_entity_data,
                    ),
                },
                extra=probatio.ALLOW_EXTRA,  # eg. "type" from WS-endpoint when validating directly
            )
            for platform, knx_schema in KNX_SCHEMA_FOR_PLATFORM.items()
        },
    ),
)

CREATE_ENTITY_BASE_SCHEMA: VolDictType = {
    probatio.Required(CONF_PLATFORM): str,
    probatio.Required(
        CONF_DATA
    ): dict,  # validated by ENTITY_STORE_DATA_SCHEMA for platform
}

UPDATE_ENTITY_BASE_SCHEMA = {
    probatio.Required(CONF_ENTITY_ID): str,
    **CREATE_ENTITY_BASE_SCHEMA,
}
