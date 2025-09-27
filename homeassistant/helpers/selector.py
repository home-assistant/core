"""Selectors for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from enum import StrEnum
from functools import cache
import importlib
from typing import Any, Literal, Required, TypedDict, cast
from uuid import UUID

import voluptuous as vol

from homeassistant.const import CONF_MODE, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import split_entity_id, valid_entity_id
from homeassistant.generated.countries import COUNTRIES
from homeassistant.util import decorator
from homeassistant.util.yaml import dumper

from . import config_validation as cv

SELECTORS: decorator.Registry[str, type[Selector]] = decorator.Registry()


def _get_selector_type_and_class(config: Any) -> tuple[str, type[Selector]]:
    """Get selector type and class."""
    if not isinstance(config, dict):
        raise vol.Invalid("Expected a dictionary")

    if len(config) != 1:
        raise vol.Invalid(f"Only one type can be specified. Found {', '.join(config)}")

    selector_type: str = list(config)[0]

    if (selector_class := SELECTORS.get(selector_type)) is None:
        raise vol.Invalid(f"Unknown selector type {selector_type} found")

    return selector_type, selector_class


def selector(config: Any) -> Selector:
    """Instantiate a selector."""
    selector_type, selector_class = _get_selector_type_and_class(config)
    return selector_class(config[selector_type])


def validate_selector(config: Any) -> dict:
    """Validate a selector."""
    selector_type, selector_class = _get_selector_type_and_class(config)
    return {selector_type: selector_class.CONFIG_SCHEMA(config[selector_type])}


class Selector[_T: Mapping[str, Any]]:
    """Base class for selectors."""

    CONFIG_SCHEMA: Callable
    config: _T
    selector_type: str

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        """Instantiate a selector."""
        self.config = self.CONFIG_SCHEMA(config)

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, Selector):
            return NotImplemented

        return self.selector_type == other.selector_type and self.config == other.config

    def serialize(self) -> dict[str, dict[str, _T]]:
        """Serialize Selector for voluptuous_serialize."""
        return {"selector": {self.selector_type: self.config}}


@cache
def _entity_feature_flag(domain: str, enum_name: str, feature_name: str) -> int:
    """Return a cached lookup of an entity feature enum.

    This will import a module from disk and is run from an executor when
    loading the services schema files.
    """
    module = importlib.import_module(f"homeassistant.components.{domain}")
    enum = getattr(module, enum_name)
    feature = getattr(enum, feature_name)
    return cast(int, feature.value)


def _validate_supported_feature(supported_feature: str) -> int:
    """Validate a supported feature and resolve an enum string to its value."""

    try:
        domain, enum, feature = supported_feature.split(".", 2)
    except ValueError as exc:
        raise vol.Invalid(
            f"Invalid supported feature '{supported_feature}', expected "
            "<domain>.<enum>.<member>"
        ) from exc

    try:
        return _entity_feature_flag(domain, enum, feature)
    except (ModuleNotFoundError, AttributeError) as exc:
        raise vol.Invalid(f"Unknown supported feature '{supported_feature}'") from exc


def _validate_supported_features(supported_features: list[str]) -> int:
    """Validate supported features and resolve enum strings to their value."""

    feature_mask = 0

    for supported_feature in supported_features:
        feature_mask |= _validate_supported_feature(supported_feature)

    return feature_mask


def make_selector_config_schema(schema_dict: dict | None = None) -> vol.Schema:
    """Make selector config schema."""
    if schema_dict is None:
        schema_dict = {}

    def none_to_empty_dict(value: Any) -> Any:
        if value is None:
            return {}
        return value

    return vol.Schema(
        vol.All(
            none_to_empty_dict,
            {
                vol.Optional("read_only"): bool,
                **schema_dict,
            },
        )
    )


class BaseSelectorConfig(TypedDict, total=False):
    """Class to common options of all selectors."""

    read_only: bool


ENTITY_FILTER_SELECTOR_CONFIG_SCHEMA = vol.Schema(
    {
        # Integration that provided the entity
        vol.Optional("integration"): str,
        # Domain the entity belongs to
        vol.Optional("domain"): vol.All(cv.ensure_list, [str]),
        # Device class of the entity
        vol.Optional("device_class"): vol.All(cv.ensure_list, [str]),
        # Features supported by the entity
        vol.Optional("supported_features"): [
            vol.All(cv.ensure_list, [str], _validate_supported_features)
        ],
    }
)


# Legacy entity selector config schema used directly under entity selectors
# is provided for backwards compatibility and remains feature frozen.
# New filtering features should be added under the `filter` key instead.
# https://github.com/home-assistant/frontend/pull/15302
_LEGACY_ENTITY_SELECTOR_CONFIG_SCHEMA_DICT = {
    # Integration that provided the entity
    vol.Optional("integration"): str,
    # Domain the entity belongs to
    vol.Optional("domain"): vol.All(cv.ensure_list, [str]),
    # Device class of the entity
    vol.Optional("device_class"): vol.All(cv.ensure_list, [str]),
}


class EntityFilterSelectorConfig(TypedDict, total=False):
    """Class to represent a single entity selector config."""

    integration: str
    domain: str | list[str]
    device_class: str | list[str]
    supported_features: list[str]


DEVICE_FILTER_SELECTOR_CONFIG_SCHEMA = vol.Schema(
    {
        # Integration linked to it with a config entry
        vol.Optional("integration"): str,
        # Manufacturer of device
        vol.Optional("manufacturer"): str,
        # Model of device
        vol.Optional("model"): str,
        # Model ID of device
        vol.Optional("model_id"): str,
    }
)


# Legacy device selector config schema used directly under device selectors
# is provided for backwards compatibility and remains feature frozen.
# New filtering features should be added under the `filter` key instead.
# https://github.com/home-assistant/frontend/pull/15302
_LEGACY_DEVICE_SELECTOR_CONFIG_SCHEMA_DICT = {
    # Integration linked to it with a config entry
    vol.Optional("integration"): str,
    # Manufacturer of device
    vol.Optional("manufacturer"): str,
    # Model of device
    vol.Optional("model"): str,
}


class DeviceFilterSelectorConfig(TypedDict, total=False):
    """Class to represent a single device selector config."""

    integration: str
    manufacturer: str
    model: str
    model_id: str


class ActionSelectorConfig(BaseSelectorConfig):
    """Class to represent an action selector config."""


@SELECTORS.register("action")
class ActionSelector(Selector[ActionSelectorConfig]):
    """Selector of an action sequence (script syntax)."""

    selector_type = "action"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: ActionSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return data


class AddonSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent an addon selector config."""

    name: str
    slug: str


@SELECTORS.register("addon")
class AddonSelector(Selector[AddonSelectorConfig]):
    """Selector of a add-on."""

    selector_type = "addon"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("name"): str,
            vol.Optional("slug"): str,
        }
    )

    def __init__(self, config: AddonSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        addon: str = vol.Schema(str)(data)
        return addon


class AreaSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent an area selector config."""

    entity: EntityFilterSelectorConfig | list[EntityFilterSelectorConfig]
    device: DeviceFilterSelectorConfig | list[DeviceFilterSelectorConfig]
    multiple: bool


@SELECTORS.register("area")
class AreaSelector(Selector[AreaSelectorConfig]):
    """Selector of a single or list of areas."""

    selector_type = "area"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("entity"): vol.All(
                cv.ensure_list,
                [ENTITY_FILTER_SELECTOR_CONFIG_SCHEMA],
            ),
            vol.Optional("device"): vol.All(
                cv.ensure_list,
                [DEVICE_FILTER_SELECTOR_CONFIG_SCHEMA],
            ),
            vol.Optional("multiple", default=False): cv.boolean,
        }
    )

    def __init__(self, config: AreaSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            area_id: str = vol.Schema(str)(data)
            return area_id
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [vol.Schema(str)(val) for val in data]


class AssistPipelineSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent an assist pipeline selector config."""


@SELECTORS.register("assist_pipeline")
class AssistPipelineSelector(Selector[AssistPipelineSelectorConfig]):
    """Selector for an assist pipeline."""

    selector_type = "assist_pipeline"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: AssistPipelineSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        pipeline: str = vol.Schema(str)(data)
        return pipeline


class AttributeSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent an attribute selector config."""

    entity_id: Required[str]
    hide_attributes: list[str]


@SELECTORS.register("attribute")
class AttributeSelector(Selector[AttributeSelectorConfig]):
    """Selector for an entity attribute."""

    selector_type = "attribute"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Required("entity_id"): cv.entity_id,
            # hide_attributes is used to hide attributes in the frontend.
            # A hidden attribute can still be provided manually.
            vol.Optional("hide_attributes"): [str],
        }
    )

    def __init__(self, config: AttributeSelectorConfig) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        attribute: str = vol.Schema(str)(data)
        return attribute


class BackupLocationSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a backup location selector config."""


@SELECTORS.register("backup_location")
class BackupLocationSelector(Selector[BackupLocationSelectorConfig]):
    """Selector of a backup location."""

    selector_type = "backup_location"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: BackupLocationSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        name: str = vol.Match(r"^(?:\/backup|\w+)$")(data)
        return name


class BooleanSelectorConfig(BaseSelectorConfig):
    """Class to represent a boolean selector config."""


@SELECTORS.register("boolean")
class BooleanSelector(Selector[BooleanSelectorConfig]):
    """Selector of a boolean value."""

    selector_type = "boolean"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: BooleanSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> bool:
        """Validate the passed selection."""
        value: bool = vol.Coerce(bool)(data)
        return value


class ColorRGBSelectorConfig(BaseSelectorConfig):
    """Class to represent a color RGB selector config."""


@SELECTORS.register("color_rgb")
class ColorRGBSelector(Selector[ColorRGBSelectorConfig]):
    """Selector of an RGB color value."""

    selector_type = "color_rgb"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: ColorRGBSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> list[int]:
        """Validate the passed selection."""
        value: list[int] = vol.All(list, vol.ExactSequence((cv.byte,) * 3))(data)
        return value


class ColorTempSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a color temp selector config."""

    unit: ColorTempSelectorUnit
    min: int
    max: int
    max_mireds: int
    min_mireds: int


class ColorTempSelectorUnit(StrEnum):
    """Possible units for a color temperature selector."""

    KELVIN = "kelvin"
    MIRED = "mired"


@SELECTORS.register("color_temp")
class ColorTempSelector(Selector[ColorTempSelectorConfig]):
    """Selector of an color temperature."""

    selector_type = "color_temp"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("unit", default=ColorTempSelectorUnit.MIRED): vol.All(
                vol.Coerce(ColorTempSelectorUnit), lambda val: val.value
            ),
            vol.Optional("min"): vol.Coerce(int),
            vol.Optional("max"): vol.Coerce(int),
            vol.Optional("max_mireds"): vol.Coerce(int),
            vol.Optional("min_mireds"): vol.Coerce(int),
        }
    )

    def __init__(self, config: ColorTempSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> int:
        """Validate the passed selection."""
        range_min = self.config.get("min")
        range_max = self.config.get("max")

        if range_min is None:
            range_min = self.config.get("min_mireds")

        if range_max is None:
            range_max = self.config.get("max_mireds")

        value: int = vol.All(
            vol.Coerce(float),
            vol.Range(
                min=range_min,
                max=range_max,
            ),
        )(data)
        return value


class ConditionSelectorConfig(BaseSelectorConfig):
    """Class to represent an condition selector config."""


@SELECTORS.register("condition")
class ConditionSelector(Selector[ConditionSelectorConfig]):
    """Selector of an condition sequence (script syntax)."""

    selector_type = "condition"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: ConditionSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return vol.Schema(cv.CONDITIONS_SCHEMA)(data)


class ConfigEntrySelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a config entry selector config."""

    integration: str


@SELECTORS.register("config_entry")
class ConfigEntrySelector(Selector[ConfigEntrySelectorConfig]):
    """Selector of a config entry."""

    selector_type = "config_entry"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("integration"): str,
        }
    )

    def __init__(self, config: ConfigEntrySelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        config: str = vol.Schema(str)(data)
        return config


class ConstantSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a constant selector config."""

    label: str
    translation_key: str
    value: str | int | bool


@SELECTORS.register("constant")
class ConstantSelector(Selector[ConstantSelectorConfig]):
    """Constant selector."""

    selector_type = "constant"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("label"): str,
            vol.Optional("translation_key"): cv.string,
            vol.Required("value"): vol.Any(str, int, bool),
        }
    )

    def __init__(self, config: ConstantSelectorConfig) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        vol.Schema(self.config["value"])(data)
        return self.config["value"]


class ConversationAgentSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a conversation agent selector config."""

    language: str


@SELECTORS.register("conversation_agent")
class ConversationAgentSelector(Selector[ConversationAgentSelectorConfig]):
    """Selector for a conversation agent."""

    selector_type = "conversation_agent"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("language"): str,
        }
    )

    def __init__(self, config: ConversationAgentSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        agent: str = vol.Schema(str)(data)
        return agent


class CountrySelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a country selector config."""

    countries: list[str]
    no_sort: bool


@SELECTORS.register("country")
class CountrySelector(Selector[CountrySelectorConfig]):
    """Selector for a single-choice country select."""

    selector_type = "country"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("countries"): [str],
            vol.Optional("no_sort", default=False): cv.boolean,
        }
    )

    def __init__(self, config: CountrySelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        country: str = vol.Schema(str)(data)
        if "countries" in self.config and (
            country not in self.config["countries"] or country not in COUNTRIES
        ):
            raise vol.Invalid(f"Value {country} is not a valid option")
        return country


class DateSelectorConfig(BaseSelectorConfig):
    """Class to represent a date selector config."""


@SELECTORS.register("date")
class DateSelector(Selector[DateSelectorConfig]):
    """Selector of a date."""

    selector_type = "date"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: DateSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        cv.date(data)
        return data


class DateTimeSelectorConfig(BaseSelectorConfig):
    """Class to represent a date time selector config."""


@SELECTORS.register("datetime")
class DateTimeSelector(Selector[DateTimeSelectorConfig]):
    """Selector of a datetime."""

    selector_type = "datetime"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: DateTimeSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        cv.datetime(data)
        return data


class DeviceSelectorConfig(BaseSelectorConfig, DeviceFilterSelectorConfig, total=False):
    """Class to represent a device selector config."""

    entity: EntityFilterSelectorConfig | list[EntityFilterSelectorConfig]
    multiple: bool
    filter: DeviceFilterSelectorConfig | list[DeviceFilterSelectorConfig]


@SELECTORS.register("device")
class DeviceSelector(Selector[DeviceSelectorConfig]):
    """Selector of a single or list of devices."""

    selector_type = "device"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            **_LEGACY_DEVICE_SELECTOR_CONFIG_SCHEMA_DICT,
            # Device has to contain entities matching this selector
            vol.Optional("entity"): vol.All(
                cv.ensure_list, [ENTITY_FILTER_SELECTOR_CONFIG_SCHEMA]
            ),
            vol.Optional("multiple", default=False): cv.boolean,
            vol.Optional("filter"): vol.All(
                cv.ensure_list,
                [DEVICE_FILTER_SELECTOR_CONFIG_SCHEMA],
            ),
        },
    )

    def __init__(self, config: DeviceSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            device_id: str = vol.Schema(str)(data)
            return device_id
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [vol.Schema(str)(val) for val in data]


class DurationSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a duration selector config."""

    enable_day: bool
    enable_millisecond: bool
    allow_negative: bool


@SELECTORS.register("duration")
class DurationSelector(Selector[DurationSelectorConfig]):
    """Selector for a duration."""

    selector_type = "duration"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            # Enable day field in frontend. A selection with `days` set is allowed
            # even if `enable_day` is not set
            vol.Optional("enable_day"): cv.boolean,
            # Enable millisecond field in frontend.
            vol.Optional("enable_millisecond"): cv.boolean,
            # Allow negative durations. Will default to False in HA Core 2025.6.0.
            vol.Optional("allow_negative"): cv.boolean,
        }
    )

    def __init__(self, config: DurationSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> dict[str, float]:
        """Validate the passed selection."""
        if self.config.get("allow_negative", True):
            cv.time_period_dict(data)
        else:
            cv.positive_time_period_dict(data)
        return cast(dict[str, float], data)


class EntitySelectorConfig(BaseSelectorConfig, EntityFilterSelectorConfig, total=False):
    """Class to represent an entity selector config."""

    exclude_entities: list[str]
    include_entities: list[str]
    multiple: bool
    reorder: bool
    filter: EntityFilterSelectorConfig | list[EntityFilterSelectorConfig]


@SELECTORS.register("entity")
class EntitySelector(Selector[EntitySelectorConfig]):
    """Selector of a single or list of entities."""

    selector_type = "entity"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            **_LEGACY_ENTITY_SELECTOR_CONFIG_SCHEMA_DICT,
            vol.Optional("exclude_entities"): [str],
            vol.Optional("include_entities"): [str],
            vol.Optional("multiple", default=False): cv.boolean,
            vol.Optional("reorder", default=False): cv.boolean,
            vol.Optional("filter"): vol.All(
                cv.ensure_list,
                [ENTITY_FILTER_SELECTOR_CONFIG_SCHEMA],
            ),
        }
    )

    def __init__(self, config: EntitySelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""

        include_entities = self.config.get("include_entities")
        exclude_entities = self.config.get("exclude_entities")

        def validate(e_or_u: str) -> str:
            e_or_u = cv.entity_id_or_uuid(e_or_u)
            if not valid_entity_id(e_or_u):
                return e_or_u
            if allowed_domains := cv.ensure_list(self.config.get("domain")):
                domain = split_entity_id(e_or_u)[0]
                if domain not in allowed_domains:
                    raise vol.Invalid(
                        f"Entity {e_or_u} belongs to domain {domain}, "
                        f"expected {allowed_domains}"
                    )
            if include_entities:
                vol.In(include_entities)(e_or_u)
            if exclude_entities:
                vol.NotIn(exclude_entities)(e_or_u)
            return e_or_u

        if not self.config["multiple"]:
            return validate(data)
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return cast(list, vol.Schema([validate])(data))  # Output is a list


class FileSelectorConfig(BaseSelectorConfig):
    """Class to represent a file selector config."""

    accept: str  # required


@SELECTORS.register("file")
class FileSelector(Selector[FileSelectorConfig]):
    """Selector of a file."""

    selector_type = "file"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/file#accept
            vol.Required("accept"): str,
        }
    )

    def __init__(self, config: FileSelectorConfig) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        if not isinstance(data, str):
            raise vol.Invalid("Value should be a string")

        UUID(data)

        return data


class FloorSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent an floor selector config."""

    entity: EntityFilterSelectorConfig | list[EntityFilterSelectorConfig]
    device: DeviceFilterSelectorConfig | list[DeviceFilterSelectorConfig]
    multiple: bool


@SELECTORS.register("floor")
class FloorSelector(Selector[FloorSelectorConfig]):
    """Selector of a single or list of floors."""

    selector_type = "floor"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("entity"): vol.All(
                cv.ensure_list,
                [ENTITY_FILTER_SELECTOR_CONFIG_SCHEMA],
            ),
            vol.Optional("device"): vol.All(
                cv.ensure_list,
                [DEVICE_FILTER_SELECTOR_CONFIG_SCHEMA],
            ),
            vol.Optional("multiple", default=False): cv.boolean,
        }
    )

    def __init__(self, config: FloorSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            floor_id: str = vol.Schema(str)(data)
            return floor_id
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [vol.Schema(str)(val) for val in data]


class IconSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent an icon selector config."""

    placeholder: str


@SELECTORS.register("icon")
class IconSelector(Selector[IconSelectorConfig]):
    """Selector for an icon."""

    selector_type = "icon"

    CONFIG_SCHEMA = make_selector_config_schema(
        {vol.Optional("placeholder"): str}
        # Frontend also has a fallbackPath option, this is not used by core
    )

    def __init__(self, config: IconSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        icon: str = vol.Schema(str)(data)
        return icon


class LabelSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a label selector config."""

    multiple: bool


@SELECTORS.register("label")
class LabelSelector(Selector[LabelSelectorConfig]):
    """Selector of a single or list of labels."""

    selector_type = "label"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("multiple", default=False): cv.boolean,
        }
    )

    def __init__(self, config: LabelSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            label_id: str = vol.Schema(str)(data)
            return label_id
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [vol.Schema(str)(val) for val in data]


class LanguageSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent an language selector config."""

    languages: list[str]
    native_name: bool
    no_sort: bool


@SELECTORS.register("language")
class LanguageSelector(Selector[LanguageSelectorConfig]):
    """Selector for an language."""

    selector_type = "language"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("languages"): [str],
            vol.Optional("native_name", default=False): cv.boolean,
            vol.Optional("no_sort", default=False): cv.boolean,
        }
    )

    def __init__(self, config: LanguageSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        language: str = vol.Schema(str)(data)
        if "languages" in self.config and language not in self.config["languages"]:
            raise vol.Invalid(f"Value {language} is not a valid option")
        return language


class LocationSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a location selector config."""

    radius: bool
    icon: str


@SELECTORS.register("location")
class LocationSelector(Selector[LocationSelectorConfig]):
    """Selector for a location."""

    selector_type = "location"

    CONFIG_SCHEMA = make_selector_config_schema(
        {vol.Optional("radius"): bool, vol.Optional("icon"): str}
    )
    DATA_SCHEMA = vol.Schema(
        {
            vol.Required("latitude"): vol.Coerce(float),
            vol.Required("longitude"): vol.Coerce(float),
            vol.Optional("radius"): vol.Coerce(float),
        }
    )

    def __init__(self, config: LocationSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> dict[str, float]:
        """Validate the passed selection."""
        location: dict[str, float] = self.DATA_SCHEMA(data)
        return location


class MediaSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a media selector config."""

    accept: list[str]


@SELECTORS.register("media")
class MediaSelector(Selector[MediaSelectorConfig]):
    """Selector for media."""

    selector_type = "media"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("accept"): [str],
        }
    )
    DATA_SCHEMA = vol.Schema(
        {
            # If accept is set, the entity_id field will not be present
            vol.Optional("entity_id"): cv.entity_id_or_uuid,
            # Although marked as optional in frontend, this field is required
            vol.Required("media_content_id"): str,
            # Although marked as optional in frontend, this field is required
            vol.Required("media_content_type"): str,
            vol.Remove("metadata"): dict,
        }
    )

    def __init__(self, config: MediaSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> dict[str, str]:
        """Validate the passed selection."""
        schema = {
            key: value
            for key, value in self.DATA_SCHEMA.schema.items()
            if key != "entity_id"
        }

        if "accept" not in self.config:
            # If accept is not set, the entity_id field is required
            schema[vol.Required("entity_id")] = cv.entity_id_or_uuid

        media: dict[str, str] = vol.Schema(schema)(data)
        return media


class NumberSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a number selector config."""

    min: float
    max: float
    step: float | Literal["any"]
    unit_of_measurement: str
    mode: NumberSelectorMode
    translation_key: str


class NumberSelectorMode(StrEnum):
    """Possible modes for a number selector."""

    BOX = "box"
    SLIDER = "slider"


def validate_slider(data: Any) -> Any:
    """Validate configuration."""
    has_min_max = "min" in data and "max" in data

    if "mode" not in data:
        data["mode"] = "slider" if has_min_max else "box"

    if data["mode"] == "slider" and not has_min_max:
        raise vol.Invalid("min and max are required in slider mode")

    return data


@SELECTORS.register("number")
class NumberSelector(Selector[NumberSelectorConfig]):
    """Selector of a numeric value."""

    selector_type = "number"

    CONFIG_SCHEMA = vol.All(
        make_selector_config_schema(
            {
                vol.Optional("min"): vol.Coerce(float),
                vol.Optional("max"): vol.Coerce(float),
                # Controls slider steps, and up/down keyboard binding for the box
                # user input is not rounded
                vol.Optional("step", default=1): vol.Any(
                    "any", vol.All(vol.Coerce(float), vol.Range(min=1e-3))
                ),
                vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
                vol.Optional(CONF_MODE): vol.All(
                    vol.Coerce(NumberSelectorMode), lambda val: val.value
                ),
                vol.Optional("translation_key"): str,
            }
        ),
        validate_slider,
    )

    def __init__(self, config: NumberSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> float:
        """Validate the passed selection."""
        value: float = vol.Coerce(float)(data)

        if "min" in self.config and value < self.config["min"]:
            raise vol.Invalid(f"Value {value} is too small")

        if "max" in self.config and value > self.config["max"]:
            raise vol.Invalid(f"Value {value} is too large")

        return value


class ObjectSelectorField(TypedDict, total=False):
    """Class to represent an object selector fields dict."""

    label: str
    required: bool
    selector: Selector | dict[str, Any]


class ObjectSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent an object selector config."""

    fields: dict[str, ObjectSelectorField]
    multiple: bool
    label_field: str
    description_field: str
    translation_key: str


@SELECTORS.register("object")
class ObjectSelector(Selector[ObjectSelectorConfig]):
    """Selector for an arbitrary object."""

    selector_type = "object"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("fields"): {
                str: {
                    vol.Required("selector"): vol.Any(Selector, validate_selector),
                    vol.Optional("required"): bool,
                    vol.Optional("label"): str,
                }
            },
            vol.Optional("multiple", default=False): bool,
            vol.Optional("label_field"): str,
            vol.Optional("description_field"): str,
            vol.Optional("translation_key"): str,
        }
    )

    def __init__(self, config: ObjectSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def serialize(self) -> dict[str, dict[str, ObjectSelectorConfig]]:
        """Serialize ObjectSelector for voluptuous_serialize."""
        _config = deepcopy(self.config)
        if "fields" in _config:
            for field_items in _config["fields"].values():
                if isinstance(field_items["selector"], ObjectSelector):
                    field_items["selector"] = field_items["selector"].serialize()
                elif isinstance(field_items["selector"], Selector):
                    field_items["selector"] = {
                        field_items["selector"].selector_type: field_items[
                            "selector"
                        ].config
                    }
        return {"selector": {self.selector_type: _config}}

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        if "fields" not in self.config:
            # Return data if no fields are defined
            return data

        if not isinstance(data, (list, dict)):
            raise vol.Invalid("Value should be a dict or a list of dicts")
        if isinstance(data, list) and not self.config["multiple"]:
            raise vol.Invalid("Value should not be a list")

        test_data = data if isinstance(data, list) else [data]

        for _config in test_data:
            for field, field_data in self.config["fields"].items():
                if field_data.get("required") and field not in _config:
                    raise vol.Invalid(f"Field {field} is required")
                if field in _config:
                    selector(field_data["selector"])(_config[field])  # type: ignore[operator]

            for key in _config:
                if key not in self.config["fields"]:
                    raise vol.Invalid(f"Field {key} is not allowed")

        return data


class QrErrorCorrectionLevel(StrEnum):
    """Possible error correction levels for QR code selector."""

    LOW = "low"
    MEDIUM = "medium"
    QUARTILE = "quartile"
    HIGH = "high"


class QrCodeSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a QR code selector config."""

    data: str
    scale: int
    error_correction_level: QrErrorCorrectionLevel


@SELECTORS.register("qr_code")
class QrCodeSelector(Selector[QrCodeSelectorConfig]):
    """QR code selector."""

    selector_type = "qr_code"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Required("data"): str,
            vol.Optional("scale"): int,
            vol.Optional("error_correction_level"): vol.All(
                vol.Coerce(QrErrorCorrectionLevel), lambda val: val.value
            ),
        }
    )

    def __init__(self, config: QrCodeSelectorConfig) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        vol.Schema(vol.Any(str, None))(data)
        return self.config["data"]


select_option = vol.All(
    dict,
    vol.Schema(
        {
            vol.Required("value"): str,
            vol.Required("label"): str,
        }
    ),
)


class SelectOptionDict(TypedDict):
    """Class to represent a select option dict."""

    value: str
    label: str


class SelectSelectorMode(StrEnum):
    """Possible modes for a select selector."""

    LIST = "list"
    DROPDOWN = "dropdown"


class SelectSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a select selector config."""

    options: Required[Sequence[SelectOptionDict] | Sequence[str]]
    multiple: bool
    custom_value: bool
    mode: SelectSelectorMode
    translation_key: str
    sort: bool


@SELECTORS.register("select")
class SelectSelector(Selector[SelectSelectorConfig]):
    """Selector for an single-choice input select."""

    selector_type = "select"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Required("options"): vol.All(vol.Any([str], [select_option])),
            vol.Optional("multiple", default=False): cv.boolean,
            vol.Optional("custom_value", default=False): cv.boolean,
            vol.Optional("mode"): vol.All(
                vol.Coerce(SelectSelectorMode), lambda val: val.value
            ),
            vol.Optional("translation_key"): cv.string,
            vol.Optional("sort", default=False): cv.boolean,
        }
    )

    def __init__(self, config: SelectSelectorConfig) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        options: Sequence[str] = []
        if config_options := self.config["options"]:
            if isinstance(config_options[0], str):
                options = cast(Sequence[str], config_options)
            else:
                options = [
                    option["value"]
                    for option in cast(Sequence[SelectOptionDict], config_options)
                ]

        parent_schema: vol.In | vol.Any = vol.In(options)
        if self.config["custom_value"]:
            parent_schema = vol.Any(parent_schema, str)

        if not self.config["multiple"]:
            return parent_schema(vol.Schema(str)(data))
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [parent_schema(vol.Schema(str)(val)) for val in data]


class StateSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent an state selector config."""

    entity_id: str
    hide_states: list[str]
    multiple: bool


@SELECTORS.register("state")
class StateSelector(Selector[StateSelectorConfig]):
    """Selector for an entity state."""

    selector_type = "state"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("hide_states"): [str],
            # The attribute to filter on, is currently deliberately not
            # configurable/exposed. We are considering separating state
            # selectors into two types: one for state and one for attribute.
            # Limiting the public use, prevents breaking changes in the future.
            # vol.Optional("attribute"): str,
            vol.Optional("multiple", default=False): cv.boolean,
        }
    )

    def __init__(self, config: StateSelectorConfig) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            state: str = vol.Schema(str)(data)
            return state
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [vol.Schema(str)(val) for val in data]


class StatisticSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a statistic selector config."""

    multiple: bool


@SELECTORS.register("statistic")
class StatisticSelector(Selector[StatisticSelectorConfig]):
    """Selector of a single or list of statistics."""

    selector_type = "statistic"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("multiple", default=False): cv.boolean,
        }
    )

    def __init__(self, config: StatisticSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""

        if not self.config["multiple"]:
            stat: str = vol.Schema(str)(data)
            return stat
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [vol.Schema(str)(val) for val in data]


class TargetSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a target selector config."""

    entity: EntityFilterSelectorConfig | list[EntityFilterSelectorConfig]
    device: DeviceFilterSelectorConfig | list[DeviceFilterSelectorConfig]


@SELECTORS.register("target")
class TargetSelector(Selector[TargetSelectorConfig]):
    """Selector of a target value (area ID, device ID, entity ID etc).

    Value should follow cv.TARGET_SERVICE_FIELDS format.
    """

    selector_type = "target"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("entity"): vol.All(
                cv.ensure_list,
                [ENTITY_FILTER_SELECTOR_CONFIG_SCHEMA],
            ),
            vol.Optional("device"): vol.All(
                cv.ensure_list,
                [DEVICE_FILTER_SELECTOR_CONFIG_SCHEMA],
            ),
        }
    )

    TARGET_SELECTION_SCHEMA = vol.Schema(cv.TARGET_SERVICE_FIELDS)

    def __init__(self, config: TargetSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> dict[str, list[str]]:
        """Validate the passed selection."""
        target: dict[str, list[str]] = self.TARGET_SELECTION_SCHEMA(data)
        return target


class TemplateSelectorConfig(BaseSelectorConfig):
    """Class to represent an template selector config."""


@SELECTORS.register("template")
class TemplateSelector(Selector[TemplateSelectorConfig]):
    """Selector for an template."""

    selector_type = "template"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: TemplateSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        template = cv.template(data)
        return template.template


class TextSelectorConfig(BaseSelectorConfig, total=False):
    """Class to represent a text selector config."""

    multiline: bool
    prefix: str
    suffix: str
    type: TextSelectorType
    autocomplete: str
    multiple: bool


class TextSelectorType(StrEnum):
    """Enum for text selector types."""

    COLOR = "color"
    DATE = "date"
    DATETIME_LOCAL = "datetime-local"
    EMAIL = "email"
    MONTH = "month"
    NUMBER = "number"
    PASSWORD = "password"
    SEARCH = "search"
    TEL = "tel"
    TEXT = "text"
    TIME = "time"
    URL = "url"
    WEEK = "week"


@SELECTORS.register("text")
class TextSelector(Selector[TextSelectorConfig]):
    """Selector for a multi-line text string."""

    selector_type = "text"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("multiline", default=False): bool,
            vol.Optional("prefix"): str,
            vol.Optional("suffix"): str,
            # The "type" controls the input field in the browser, the resulting
            # data can be any string so we don't validate it.
            vol.Optional("type"): vol.All(
                vol.Coerce(TextSelectorType), lambda val: val.value
            ),
            vol.Optional("autocomplete"): str,
            vol.Optional("multiple", default=False): bool,
        }
    )

    def __init__(self, config: TextSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            text: str = vol.Schema(str)(data)
            return text
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [vol.Schema(str)(val) for val in data]


class ThemeSelectorConfig(BaseSelectorConfig):
    """Class to represent a theme selector config."""


@SELECTORS.register("theme")
class ThemeSelector(Selector[ThemeSelectorConfig]):
    """Selector for an theme."""

    selector_type = "theme"

    CONFIG_SCHEMA = make_selector_config_schema(
        {
            vol.Optional("include_default", default=False): cv.boolean,
        }
    )

    def __init__(self, config: ThemeSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        theme: str = vol.Schema(str)(data)
        return theme


class TimeSelectorConfig(BaseSelectorConfig):
    """Class to represent a time selector config."""


@SELECTORS.register("time")
class TimeSelector(Selector[TimeSelectorConfig]):
    """Selector of a time value."""

    selector_type = "time"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: TimeSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        cv.time(data)
        return cast(str, data)


class TriggerSelectorConfig(BaseSelectorConfig):
    """Class to represent an trigger selector config."""


@SELECTORS.register("trigger")
class TriggerSelector(Selector[TriggerSelectorConfig]):
    """Selector of a trigger sequence (script syntax)."""

    selector_type = "trigger"

    CONFIG_SCHEMA = make_selector_config_schema()

    def __init__(self, config: TriggerSelectorConfig | None = None) -> None:
        """Instantiate a selector."""
        super().__init__(config)

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return vol.Schema(cv.TRIGGER_SCHEMA)(data)


dumper.add_representer(
    Selector,
    lambda dumper, value: dumper.represent_odict(
        dumper, "tag:yaml.org,2002:map", value.serialize()
    ),
)
