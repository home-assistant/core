"""Selectors for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal, TypedDict, cast, overload

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.const import CONF_MODE, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import split_entity_id, valid_entity_id
from homeassistant.util import decorator

from . import config_validation as cv

SELECTORS: decorator.Registry[str, type[Selector]] = decorator.Registry()


class SelectorType(StrEnum):
    """Enum to represent all selector types."""

    ACTION = "action"
    ADDON = "addon"
    AREA = "area"
    ATTRIBUTE = "attribute"
    BOOLEAN = "boolean"
    COLOR_RGB = "color_rgb"
    COLOR_TEMP = "color_temp"
    DATE = "date"
    DATETIME = "datetime"
    DEVICE = "device"
    DURATION = "duration"
    ENTITY = "entity"
    ICON = "icon"
    LOCATION = "location"
    MEDIA = "media"
    NUMBER = "number"
    OBJECT = "object"
    SELECT = "select"
    TARGET = "target"
    TEXT = "text"
    THEME = "theme"
    TIME = "time"


def _get_selector_class(config: Any) -> type[Selector]:
    """Get selector class type."""
    if not isinstance(config, dict):
        raise vol.Invalid("Expected a dictionary")

    if len(config) != 1:
        raise vol.Invalid(f"Only one type can be specified. Found {', '.join(config)}")

    selector_type: str = list(config)[0]

    if (selector_class := SELECTORS.get(selector_type)) is None:
        raise vol.Invalid(f"Unknown selector type {selector_type} found")

    return selector_class


def validate_selector(config: Any) -> dict:
    """Validate a selector."""
    selector_class = _get_selector_class(config)
    selector_type = list(config)[0]

    # Selectors can be empty
    if config[selector_type] is None:
        return {selector_type: {}}

    return {
        selector_type: cast(dict, selector_class.CONFIG_SCHEMA(config[selector_type]))
    }


@overload
def selector(
    selector_type: Literal[SelectorType.ACTION], config: ActionSelectorDict
) -> ActionSelector:
    """Instantiate an action selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.ADDON], config: AddonSelectorDict
) -> AddonSelector:
    """Instantiate an addon selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.AREA], config: AreaSelectorDict
) -> AreaSelector:
    """Instantiate an area selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.ATTRIBUTE], config: AttributeSelectorDict
) -> AttributeSelector:
    """Instantiate an attribute selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.BOOLEAN], config: BooleanSelectorDict
) -> BooleanSelector:
    """Instantiate a boolean selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.COLOR_RGB], config: ColorRGBSelectorDict
) -> ColorRGBSelector:
    """Instantiate a color_rgb selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.COLOR_TEMP], config: ColorTempSelectorDict
) -> ColorTempSelector:
    """Instantiate a color_temp selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.DATE], config: DateSelectorDict
) -> DateSelector:
    """Instantiate a date selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.DATETIME], config: DateTimeSelectorDict
) -> DateTimeSelector:
    """Instantiate a datetime selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.DEVICE], config: DeviceSelectorDict
) -> DeviceSelector:
    """Instantiate a device selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.DURATION], config: DurationSelectorDict
) -> DurationSelector:
    """Instantiate a duration selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.ENTITY], config: EntitySelectorDict
) -> EntitySelector:
    """Instantiate a entity selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.ICON], config: IconSelectorDict
) -> IconSelector:
    """Instantiate a icon selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.LOCATION], config: LocationSelectorDict
) -> LocationSelector:
    """Instantiate a location selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.MEDIA], config: MediaSelectorDict
) -> MediaSelector:
    """Instantiate a media selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.NUMBER], config: NumberSelectorDict
) -> NumberSelector:
    """Instantiate a number selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.OBJECT], config: ObjectSelectorDict
) -> ObjectSelector:
    """Instantiate an object selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.SELECT], config: SelectSelectorDict
) -> SelectSelector:
    """Instantiate a select selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.TARGET], config: TargetSelectorDict
) -> TargetSelector:
    """Instantiate a target selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.TEXT], config: TextSelectorDict
) -> TextSelector:
    """Instantiate a text selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.THEME], config: ThemeSelectorDict
) -> ThemeSelector:
    """Instantiate a theme selector."""


@overload
def selector(
    selector_type: Literal[SelectorType.TIME], config: TimeSelectorDict
) -> TimeSelector:
    """Instantiate a time selector."""


def selector(selector_type: SelectorType, config: Any) -> Selector:
    """Instantiate a selector."""
    if (selector_class := SELECTORS.get(selector_type)) is None:
        raise vol.Invalid(f"Unknown selector type {selector_type} found")

    # selector config can be empty
    if config is None:
        config = {}

    return selector_class({selector_type: config})


class Selector:
    """Base class for selectors."""

    CONFIG_SCHEMA: Callable
    config: Any
    selector_type: str

    def __init__(self, config: Any) -> None:
        """Instantiate a selector."""
        self.config = self.CONFIG_SCHEMA(config[self.selector_type])

    def serialize(self) -> Any:
        """Serialize Selector for voluptuous_serialize."""
        return {"selector": {self.selector_type: self.config}}


SINGLE_ENTITY_SELECTOR_CONFIG_SCHEMA = vol.Schema(
    {
        # Integration that provided the entity
        vol.Optional("integration"): str,
        # Domain the entity belongs to
        vol.Optional("domain"): vol.Any(str, [str]),
        # Device class of the entity
        vol.Optional("device_class"): str,
    }
)


class SingleEntitySelectorDict(TypedDict, total=False):
    """Class to represent a single entity selector dict."""

    integration: str
    domain: str
    device_class: str


SINGLE_DEVICE_SELECTOR_CONFIG_SCHEMA = vol.Schema(
    {
        # Integration linked to it with a config entry
        vol.Optional("integration"): str,
        # Manufacturer of device
        vol.Optional("manufacturer"): str,
        # Model of device
        vol.Optional("model"): str,
        # Device has to contain entities matching this selector
        vol.Optional("entity"): SINGLE_ENTITY_SELECTOR_CONFIG_SCHEMA,
    }
)


class SingleDeviceSelectorDict(TypedDict, total=False):
    """Class to represent a single device selector dict."""

    integration: str
    manufacturer: str
    model: str
    entity: SingleEntitySelectorDict


class ActionSelectorDict(TypedDict):
    """Class to represent an action selector dict."""


@SELECTORS.register(SelectorType.ACTION)
class ActionSelector(Selector):
    """Selector of an action sequence (script syntax)."""

    selector_type = SelectorType.ACTION

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return data


class AddonSelectorDict(TypedDict, total=False):
    """Class to represent an addon selector dict."""

    name: str
    slug: str


@SELECTORS.register(SelectorType.ADDON)
class AddonSelector(Selector):
    """Selector of a add-on."""

    selector_type = SelectorType.ADDON

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("name"): str,
            vol.Optional("slug"): str,
        }
    )

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        addon: str = vol.Schema(str)(data)
        return addon


class AreaSelectorDict(TypedDict, total=False):
    """Class to represent an area selector dict."""

    entity: SingleEntitySelectorDict
    device: SingleDeviceSelectorDict
    multiple: bool


@SELECTORS.register(SelectorType.AREA)
class AreaSelector(Selector):
    """Selector of a single or list of areas."""

    selector_type = SelectorType.AREA

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("entity"): SINGLE_ENTITY_SELECTOR_CONFIG_SCHEMA,
            vol.Optional("device"): SINGLE_DEVICE_SELECTOR_CONFIG_SCHEMA,
            vol.Optional("multiple", default=False): cv.boolean,
        }
    )

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            area_id: str = vol.Schema(str)(data)
            return area_id
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [vol.Schema(str)(val) for val in data]


class AttributeSelectorDict(TypedDict):
    """Class to represent an attribute selector dict."""

    entity_id: str


@SELECTORS.register(SelectorType.ATTRIBUTE)
class AttributeSelector(Selector):
    """Selector for an entity attribute."""

    selector_type = SelectorType.ATTRIBUTE

    CONFIG_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.entity_id})

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        attribute: str = vol.Schema(str)(data)
        return attribute


class BooleanSelectorDict(TypedDict):
    """Class to represent a boolean selector dict."""


@SELECTORS.register(SelectorType.BOOLEAN)
class BooleanSelector(Selector):
    """Selector of a boolean value."""

    selector_type = SelectorType.BOOLEAN

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> bool:
        """Validate the passed selection."""
        value: bool = vol.Coerce(bool)(data)
        return value


class ColorRGBSelectorDict(TypedDict):
    """Class to represent a color RGB selector dict."""


@SELECTORS.register(SelectorType.COLOR_RGB)
class ColorRGBSelector(Selector):
    """Selector of an RGB color value."""

    selector_type = SelectorType.COLOR_RGB

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> list[int]:
        """Validate the passed selection."""
        value: list[int] = vol.All(list, vol.ExactSequence((cv.byte,) * 3))(data)
        return value


class ColorTempSelectorDict(TypedDict, total=False):
    """Class to represent a color temp selector dict."""

    max_mireds: int
    min_mireds: int


@SELECTORS.register(SelectorType.COLOR_TEMP)
class ColorTempSelector(Selector):
    """Selector of an color temperature."""

    selector_type = SelectorType.COLOR_TEMP

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("max_mireds"): vol.Coerce(int),
            vol.Optional("min_mireds"): vol.Coerce(int),
        }
    )

    def __call__(self, data: Any) -> int:
        """Validate the passed selection."""
        value: int = vol.All(
            vol.Coerce(float),
            vol.Range(
                min=self.config.get("min_mireds"),
                max=self.config.get("max_mireds"),
            ),
        )(data)
        return value


class DateSelectorDict(TypedDict):
    """Class to represent a date selector dict."""


@SELECTORS.register(SelectorType.DATE)
class DateSelector(Selector):
    """Selector of a date."""

    selector_type = SelectorType.DATE

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        cv.date(data)
        return data


class DateTimeSelectorDict(TypedDict):
    """Class to represent a date time selector dict."""


@SELECTORS.register(SelectorType.DATETIME)
class DateTimeSelector(Selector):
    """Selector of a datetime."""

    selector_type = SelectorType.DATETIME

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        cv.datetime(data)
        return data


class DeviceSelectorDict(TypedDict, total=False):
    """Class to represent a device selector dict."""

    integration: str
    manufacturer: str
    model: str
    entity: SingleEntitySelectorDict
    multiple: bool


@SELECTORS.register(SelectorType.DEVICE)
class DeviceSelector(Selector):
    """Selector of a single or list of devices."""

    selector_type = SelectorType.DEVICE

    CONFIG_SCHEMA = SINGLE_DEVICE_SELECTOR_CONFIG_SCHEMA.extend(
        {vol.Optional("multiple", default=False): cv.boolean}
    )

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            device_id: str = vol.Schema(str)(data)
            return device_id
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [vol.Schema(str)(val) for val in data]


class DurationSelectorDict(TypedDict, total=False):
    """Class to represent a duration selector dict."""

    enable_day: bool


@SELECTORS.register(SelectorType.DURATION)
class DurationSelector(Selector):
    """Selector for a duration."""

    selector_type = SelectorType.DURATION

    CONFIG_SCHEMA = vol.Schema(
        {
            # Enable day field in frontend. A selection with `days` set is allowed
            # even if `enable_day` is not set
            vol.Optional("enable_day"): cv.boolean,
        }
    )

    def __call__(self, data: Any) -> dict[str, float]:
        """Validate the passed selection."""
        cv.time_period_dict(data)
        return cast(dict[str, float], data)


class EntitySelectorDict(SingleEntitySelectorDict, total=False):
    """Class to represent an entity selector dict."""

    exclude_entities: list[str]
    include_entities: list[str]
    multiple: bool


@SELECTORS.register(SelectorType.ENTITY)
class EntitySelector(Selector):
    """Selector of a single or list of entities."""

    selector_type = SelectorType.ENTITY

    CONFIG_SCHEMA = SINGLE_ENTITY_SELECTOR_CONFIG_SCHEMA.extend(
        {
            vol.Optional("exclude_entities"): [str],
            vol.Optional("include_entities"): [str],
            vol.Optional("multiple", default=False): cv.boolean,
        }
    )

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


class IconSelectorDict(TypedDict, total=False):
    """Class to represent an icon selector dict."""

    placeholder: str


@SELECTORS.register(SelectorType.ICON)
class IconSelector(Selector):
    """Selector for an icon."""

    selector_type = SelectorType.ICON

    CONFIG_SCHEMA = vol.Schema(
        {vol.Optional("placeholder"): str}
        # Frontend also has a fallbackPath option, this is not used by core
    )

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        icon: str = vol.Schema(str)(data)
        return icon


class LocationSelectorDict(TypedDict, total=False):
    """Class to represent a location selector dict."""

    radius: bool
    icon: str


@SELECTORS.register(SelectorType.LOCATION)
class LocationSelector(Selector):
    """Selector for a location."""

    selector_type = SelectorType.LOCATION

    CONFIG_SCHEMA = vol.Schema(
        {vol.Optional("radius"): bool, vol.Optional("icon"): str}
    )
    DATA_SCHEMA = vol.Schema(
        {
            vol.Required("latitude"): float,
            vol.Required("longitude"): float,
            vol.Optional("radius"): float,
        }
    )

    def __call__(self, data: Any) -> dict[str, float]:
        """Validate the passed selection."""
        location: dict[str, float] = self.DATA_SCHEMA(data)
        return location


class MediaSelectorDict(TypedDict):
    """Class to represent a media selector dict."""


@SELECTORS.register(SelectorType.MEDIA)
class MediaSelector(Selector):
    """Selector for media."""

    selector_type = SelectorType.MEDIA

    CONFIG_SCHEMA = vol.Schema({})
    DATA_SCHEMA = vol.Schema(
        {
            # Although marked as optional in frontend, this field is required
            vol.Required("entity_id"): cv.entity_id_or_uuid,
            # Although marked as optional in frontend, this field is required
            vol.Required("media_content_id"): str,
            # Although marked as optional in frontend, this field is required
            vol.Required("media_content_type"): str,
            vol.Remove("metadata"): dict,
        }
    )

    def __call__(self, data: Any) -> dict[str, float]:
        """Validate the passed selection."""
        media: dict[str, float] = self.DATA_SCHEMA(data)
        return media


class NumberSelectorDict(TypedDict, total=False):
    """Class to represent a number selector dict."""

    min: float
    max: float
    step: float
    unit_of_measurement: str
    mode: NumberSelectorMode


class NumberSelectorMode(StrEnum):
    """Possible modes for a number selector."""

    BOX = "box"
    SLIDER = "slider"


def has_min_max_if_slider(data: Any) -> Any:
    """Validate configuration."""
    if data["mode"] == "box":
        return data

    if "min" not in data or "max" not in data:
        raise vol.Invalid("min and max are required in slider mode")

    return data


@SELECTORS.register(SelectorType.NUMBER)
class NumberSelector(Selector):
    """Selector of a numeric value."""

    selector_type = SelectorType.NUMBER

    CONFIG_SCHEMA = vol.All(
        vol.Schema(
            {
                vol.Optional("min"): vol.Coerce(float),
                vol.Optional("max"): vol.Coerce(float),
                # Controls slider steps, and up/down keyboard binding for the box
                # user input is not rounded
                vol.Optional("step", default=1): vol.All(
                    vol.Coerce(float), vol.Range(min=1e-3)
                ),
                vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
                vol.Optional(CONF_MODE, default=NumberSelectorMode.SLIDER): vol.Coerce(
                    NumberSelectorMode
                ),
            }
        ),
        has_min_max_if_slider,
    )

    def __call__(self, data: Any) -> float:
        """Validate the passed selection."""
        value: float = vol.Coerce(float)(data)

        if "min" in self.config and value < self.config["min"]:
            raise vol.Invalid(f"Value {value} is too small")

        if "max" in self.config and value > self.config["max"]:
            raise vol.Invalid(f"Value {value} is too large")

        return value


class ObjectSelectorDict(TypedDict):
    """Class to represent an object selector dict."""


@SELECTORS.register(SelectorType.OBJECT)
class ObjectSelector(Selector):
    """Selector for an arbitrary object."""

    selector_type = SelectorType.OBJECT

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return data


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
    """Possible modes for a number selector."""

    LIST = "list"
    DROPDOWN = "dropdown"


class SelectSelectorDict(TypedDict, total=False):
    """Class to represent a select selector dict."""

    options: Sequence[SelectOptionDict] | Sequence[str]  # required
    multiple: bool
    custom_value: bool
    mode: SelectSelectorMode


@SELECTORS.register(SelectorType.SELECT)
class SelectSelector(Selector):
    """Selector for an single-choice input select."""

    selector_type = SelectorType.SELECT

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required("options"): vol.All(vol.Any([str], [select_option])),
            vol.Optional("multiple", default=False): cv.boolean,
            vol.Optional("custom_value", default=False): cv.boolean,
            vol.Optional("mode"): vol.Coerce(SelectSelectorMode),
        }
    )

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        options = []
        if self.config["options"]:
            if isinstance(self.config["options"][0], str):
                options = self.config["options"]
            else:
                options = [option["value"] for option in self.config["options"]]

        parent_schema = vol.In(options)
        if self.config["custom_value"]:
            parent_schema = vol.Any(parent_schema, str)

        if not self.config["multiple"]:
            return parent_schema(vol.Schema(str)(data))
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [parent_schema(vol.Schema(str)(val)) for val in data]


class TargetSelectorDict(TypedDict, total=False):
    """Class to represent a target selector dict."""

    entity: SingleEntitySelectorDict
    device: SingleDeviceSelectorDict


@SELECTORS.register(SelectorType.TARGET)
class TargetSelector(Selector):
    """Selector of a target value (area ID, device ID, entity ID etc).

    Value should follow cv.TARGET_SERVICE_FIELDS format.
    """

    selector_type = SelectorType.TARGET

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("entity"): SINGLE_ENTITY_SELECTOR_CONFIG_SCHEMA,
            vol.Optional("device"): SINGLE_DEVICE_SELECTOR_CONFIG_SCHEMA,
        }
    )

    TARGET_SELECTION_SCHEMA = vol.Schema(cv.TARGET_SERVICE_FIELDS)

    def __call__(self, data: Any) -> dict[str, list[str]]:
        """Validate the passed selection."""
        target: dict[str, list[str]] = self.TARGET_SELECTION_SCHEMA(data)
        return target


class TextSelectorDict(TypedDict, total=False):
    """Class to represent a text selector dict."""

    multiline: bool
    suffix: str
    type: TextSelectorType


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


@SELECTORS.register(SelectorType.TEXT)
class TextSelector(Selector):
    """Selector for a multi-line text string."""

    selector_type = SelectorType.TEXT

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("multiline", default=False): bool,
            vol.Optional("suffix"): str,
            # The "type" controls the input field in the browser, the resulting
            # data can be any string so we don't validate it.
            vol.Optional("type"): vol.Coerce(TextSelectorType),
        }
    )

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        text: str = vol.Schema(str)(data)
        return text


class ThemeSelectorDict(TypedDict):
    """Class to represent a theme selector dict."""


@SELECTORS.register(SelectorType.THEME)
class ThemeSelector(Selector):
    """Selector for an theme."""

    selector_type = SelectorType.THEME

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        theme: str = vol.Schema(str)(data)
        return theme


class TimeSelectorDict(TypedDict):
    """Class to represent a time selector dict."""


@SELECTORS.register(SelectorType.TIME)
class TimeSelector(Selector):
    """Selector of a time value."""

    selector_type = SelectorType.TIME

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        cv.time(data)
        return cast(str, data)
