"""Property in LG ThinQ device profile."""

from __future__ import annotations

import inspect
import logging
import math
import re
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Awaitable, Callable

from homeassistant.const import Platform
from thinqconnect.const import PROPERTY_READABLE, PROPERTY_WRITABLE
from thinqconnect.devices.connect_device import TYPE, UNIT, ConnectBaseDevice
from thinqconnect.thinq_api import ThinQApiResponse

from .const import POWER_ON, Profile
from .device import ConnectBaseDevice, LGDevice

_LOGGER = logging.getLogger(__name__)


class Range:
    """This class contains a range type of data."""

    def __init__(self, value: dict):
        """Initialize values."""
        self._max = value.get("max", 1)
        self._min = value.get("min", 0)
        self._step = value.get("step", 1)

    @property
    def max(self) -> int | float:
        """Returns the maximum value."""
        return self._max

    @property
    def min(self) -> int | float:
        """Returns the minimum value."""
        return self._min

    @min.setter
    def min(self, value: int | float):
        """Returns the minimum value."""
        self._min = value

    @property
    def step(self) -> int | float:
        """Returns the step value."""
        return self._step

    def validate(self, value: Any) -> bool:
        """Checks if the given value is valid."""
        if (
            isinstance(value, int) or isinstance(value, float)
        ) and math.isclose(value % self.step, 0):
            return value <= self.max and value >= self.min

        return False

    def clamp(self, value: int | float) -> int | float:
        """Force to clamp the value."""
        candidate: float = int(value // self.step) * self.step
        return max(min(candidate, self.max), self.min)

    def to_options(self) -> list[str]:
        """Convert data to options list."""
        options: list[str] = []

        value = self.min
        while value < self.max:
            options.append(str(value))
            value += self.step

        options.append(str(self.max))
        return options

    @classmethod
    def create(cls, profile: Profile) -> Range:
        """Create a range instance."""
        value: Any = profile.get(PROPERTY_WRITABLE) or profile.get(
            PROPERTY_READABLE
        )
        return cls(value) if isinstance(value, dict) else None

    @staticmethod
    def range_to_options(profile: Profile) -> list[str]:
        """Create a range instance and then convert it to options."""
        range = Range.create(profile)
        return range.to_options() if range else []

    def __str__(self) -> str:
        """Returns a string representation."""
        return f"Range(max={self._max}, min={self._min}, step={self._step})"


class PropertyFeature(Enum):
    """Features of properties for property group."""

    POWER = auto()
    STATE = auto()
    BATTERY = auto()
    CURRENT_TEMP = auto()
    TARGET_TEMP = auto()
    HEAT_TARGET_TEMP = auto()
    COOL_TARGET_TEMP = auto()
    TWO_SET_CURRENT_TEMP = auto()
    TWO_SET_HEAT_TARGET_TEMP = auto()
    TWO_SET_COOL_TARGET_TEMP = auto()
    CURRENT_HUMIDITY = auto()
    TARGET_HUMIDITY = auto()
    OP_MODE = auto()
    HVAC_MODE = auto()
    FAN_MODE = auto()


class PropertyMode(Enum):
    """Modes for how to control properties."""

    # The default operation mode.
    DEFAULT = auto()

    # A mode that dynamically selects from the list of keys assigned to
    # children.
    SELECTIVE = auto()

    # A mode that combines the key list assigned to children and
    # operates like a single property.
    COMBINED = auto()

    # A mode that has several child properties with feature assigned to
    # featured map.
    FEATURED = auto()


@dataclass(kw_only=True)
class PropertyInfo:
    """A data class contains an information for creating property."""

    # The property key for use in SDK must be snake_case string.
    key: str

    # The property control mode.
    mode: PropertyMode = PropertyMode.DEFAULT

    # Optional, a list of child properties.
    # Required for mode 'SELECTIVE' or 'COMBINED'.
    children: tuple[PropertyInfo] | None = None

    # Optional, an information of the property that provide unit.
    # It operates only in DEFAULT mode and is ignored even if other
    # modes are set.
    unit_info: PropertyInfo | None = None

    # Optional, when a feature is requested from the parent property.
    feature: PropertyFeature | None = None

    # Optional, if true then validate property value itself.
    self_validation: bool = False

    # Optional, if the value should be converted before calling api.
    value_converter: Callable[[Any], Any] | None = None

    # Optional, if the value received as a result of the api call is
    # needed to be converted in a specific format.
    value_formatter: Callable[[Any], Any] | None = None

    # Optional, if an alternative options is needed. The arguments of
    # of this method must be profile of the proerty.
    alt_options_provider: Callable[[Profile], list[str]] | None = None

    # Optional, if an alternative get method is needed. The arguments
    # of this method must be property itself.
    alt_get_method: Callable[[Property], Any] | None = None

    # Optional, for UNSET washer's relative timer.
    # It's min is 3, but for cancel the timer we need 0
    modify_minimum_range: bool = False

    # Optional, for absolute timer hint. ex) "Input 24-hour clock"
    alt_text_hint: str | None = None

    # Optional, for targetTemperature is not range"
    alt_range: dict | None = None

    # Optional, if an alternative post method is needed. The arguments
    # of this method must be property itself and value.
    alt_post_method: (
        Callable[[Property, Any], Awaitable[ThinQApiResponse]] | None
    ) = None

    # Optional, if an alternative validate creation method is needed.
    # The arguments of this method must be readable and writable flags
    # from the peoperty profile.
    alt_validate_creation: Callable[[bool, bool], bool] = None


class Property:
    """A class that implementats lg thinq property."""

    def __init__(
        self,
        device: LGDevice,
        info: PropertyInfo,
        *,
        profile: Profile | None = None,
        location: str | None = None,
    ) -> None:
        """Initialize a property."""
        self._device: LGDevice = device
        self._api: ConnectBaseDevice = (
            device.api.get_sub_device(location) or device.api
        )
        self._info: PropertyInfo = info
        self._profile: Profile = profile or {}
        self._location: str | None = location
        self._children: deque[Property] = deque()
        self._featured_map: dict[PropertyFeature, Property] = {}
        self._getter_name: str | None = self._retrieve_getter_name()
        self._setter_name: str | None = self._retrieve_setter_name()
        self._setter: Callable[[Any], Awaitable] | None = (
            self._retrieve_setter()
        )
        self._unit: str | None = self._retrieve_unit()
        self._unit_provider: Property | None = None
        self._range: Range | None = self._retrieve_range()
        self._options: list[str] | None = self._retrieve_options()

    @property
    def device(self) -> LGDevice:
        """Returns the device."""
        return self._device

    @property
    def api(self) -> ConnectBaseDevice:
        """Returns the device api."""
        return self._api

    @property
    def info(self) -> PropertyInfo:
        """Returns the property info."""
        return self._info

    @property
    def profile(self) -> Profile:
        """Returns the profile data."""
        return self._profile

    @property
    def location(self) -> str | None:
        """Returns the location."""
        return self._location

    @property
    def key(self) -> str:
        """Returns the key."""
        return self.info.key

    @property
    def range(self) -> Range | None:
        """Returns the range if exist."""
        return self._range

    @property
    def options(self) -> list[str] | None:
        """Returns the options if exist."""
        return self._options

    @property
    def unit(self) -> str | None:
        """Returns the unit if exist."""
        return self._unit

    @property
    def readable(self) -> bool:
        """Returns ture if readable property, otherwise false."""
        return self.profile.get(PROPERTY_READABLE, False)

    @property
    def writable(self) -> bool:
        """Returns ture if writable property, otherwise false."""
        return self.profile.get(PROPERTY_WRITABLE, False)

    @property
    def has_child(self) -> bool:
        """Check whether the property has a child."""
        return self._children or self._featured_map

    @property
    def tag(self) -> str:
        """Returns the tag string."""
        if self.location:
            return f"[{self.device.name}][{self.location}][{self.key}]"
        else:
            return f"[{self.device.name}][{self.key}]"

    def add_child(self, child: Property) -> None:
        """Add a child property."""
        self._children.append(child)

    def add_feature(self, feature: PropertyFeature, child: Property) -> None:
        """Add feature with a child property."""
        if feature in self._featured_map:
            raise RuntimeError(f"{self.tag} {feature} is already exist.")

        self._featured_map[feature] = child

    def set_unit_provider(self, unit_provider: Property) -> None:
        """Set an unit provider."""
        self._unit_provider = unit_provider

    def get_featured_property(
        self, feature: PropertyFeature
    ) -> Property | None:
        """Returns the featured property from the map."""
        return self._featured_map.get(feature)

    def _retrieve_getter_name(self) -> str:
        """Retrieve the getter name."""
        return self.key

    def _retrieve_setter_name(self) -> str:
        """Retrieve the setter name."""
        return f"set_{self.key}"

    def _retrieve_setter(self) -> Callable[[Any], Awaitable] | None:
        """Retrieve the setter method."""
        for name, func in inspect.getmembers(self.api):
            if inspect.iscoroutinefunction(func) and name == self._setter_name:
                return func

        return None

    def _retrieve_unit(self) -> str | None:
        """Retrieve a unit of data from the given profile."""
        unit: Any = self.profile.get(UNIT)

        if isinstance(unit, dict):
            unit = unit.get("value")
            if isinstance(unit, dict):
                unit = unit.get(PROPERTY_WRITABLE) or unit.get(
                    PROPERTY_READABLE
                )

        if isinstance(unit, str):
            _LOGGER.debug("%s _retrieve_unit: %s", self.tag, unit)
            return unit

        return None

    def _retrieve_range(self) -> Range | None:
        """Retrieve a range type of data from the given profile."""
        range = Range.create(self.profile)
        if range and self.info.modify_minimum_range:
            range.min = 0

        if range:
            _LOGGER.debug("%s retrieve_range: %s", self.tag, range)
            return range

        if self.info.alt_range:
            return Range(self.info.alt_range)

        return None

    def _retrieve_options(self) -> list[str] | None:
        """Retrieve a list of options from the given profile."""
        options: list[str] = None

        # Use alternative method instead of default logic if exist.
        if inspect.isfunction(self.info.alt_options_provider):
            options = self.info.alt_options_provider(self.profile)

            _LOGGER.debug("%s retrieve_alt_options: %s", self.tag, options)
            return options

        type: Any = self.profile.get(TYPE)
        value: Any = self.profile.get(PROPERTY_WRITABLE) or self.profile.get(
            PROPERTY_READABLE
        )

        options: list[str] = None
        if type == "enum" and isinstance(value, list):
            options = list(value)
        elif type == "boolean" and value is True:
            options = [str(False), str(True)]
        else:
            return None

        _LOGGER.debug("%s retrieve_options: %s", self.tag, options)
        return options

    def _validate_value(self, value: Any) -> bool:
        """Validate the given value."""
        if self.range:
            return self.range.validate(value)
        elif self.options and isinstance(value, str):
            return value in self.options

        return True

    def _get_value(self, key_for_dict_value: str) -> Any:
        """Get the value from the api and update unit internally."""
        value: Any = self.api.get_status(self._getter_name)

        # The data of some properties has both value and unit in
        # dictionary. In this case, the unit in the dictionary has
        # higher priority than the unit provided by the unit provider.
        if isinstance(value, dict):
            self._unit = value.get(UNIT)
            value = value.get(key_for_dict_value)
        elif self._unit_provider:
            self._unit = self._unit_provider.get_value()

        _LOGGER.debug(
            "%s get_value: %s (%s)", self.tag, value, self._getter_name
        )
        return value

    def get_value(self, key_for_dict_value: str = None) -> Any:
        """Returns the value of property."""
        # Get the value first.
        value: Any = None
        if self.info.alt_get_method:
            value = self.info.alt_get_method(self)
            _LOGGER.debug(
                "%s get_value: %s (%s)", self.tag, value, "alt_get_method"
            )
        else:
            value = self._get_value(key_for_dict_value)

        # Validate the value itself if needed.
        if self.info.self_validation:
            value = value if self._validate_value(value) else None

        # Format the value before returning if needed.
        if inspect.isfunction(self.info.value_formatter):
            value = self.info.value_formatter(value)

        if not value and self.info.alt_text_hint:
            value = self.info.alt_text_hint

        return value

    def get_value_as_bool(self) -> bool:
        """Returns the value of property as boolean type."""
        value: Any = self.get_value()
        if isinstance(value, str):
            return value == POWER_ON or value.lower() == "true"
        else:
            return bool(value)

    async def _async_post_value(self, value: Any) -> ThinQApiResponse | None:
        """Post the value."""
        if value is None:
            raise ValueError(f"value is not exist.")
        if not self._setter:
            raise TypeError(f"{self._setter_name} is not exist.")

        _LOGGER.debug(
            "%s async_post_value: %s (%s)",
            self.tag,
            value,
            self._setter_name,
        )
        return await self._setter(value)

    async def async_post_value(self, value: Any) -> ThinQApiResponse:
        """Request to post the property value."""
        if not self.writable:
            _LOGGER.error(
                "%s Failed to async_post_value: %s", self.tag, "not writable."
            )
            self.device.handle_error(
                "The control command is not supported.", "-1"
            )
            return None

        if inspect.isfunction(self.info.value_converter):
            value = self.info.value_converter(value)

        result: ThinQApiResponse = None
        try:
            result = await self._async_post_value(value)
        except ValueError as e:
            _LOGGER.error(
                "%s Failed to async_post_value: %s, %s",
                self.tag,
                value,
                e,
            )
        except TypeError as e:
            if inspect.isfunction(self.info.alt_post_method):
                _LOGGER.debug(
                    "%s async_post_value: %s (%s)",
                    self.tag,
                    value,
                    "alt_post_method",
                )
                result = await self.info.alt_post_method(self, value)
            else:
                _LOGGER.error(
                    "%s Failed to async_post_value: %s (%s), %s",
                    self.tag,
                    value,
                    self._setter_name,
                    e,
                )

        if result is not None:
            self.device.handle_api_response(result, handle_error=True)
        else:
            self.device.handle_error("Not supported.", "-1")

        return result

    def __str__(self) -> str:
        """Returns a string expression."""
        if self.location:
            return f"Property({self.device.name}:{self.location}:{self.key})"
        else:
            return f"Property({self.device.name}:{self.key})"


class CombinedProperty(Property):
    """A property that operates by combining several properties."""

    @property
    def readable(self) -> bool:
        """Returns ture if readable property, otherwise false."""
        for child in self._children:
            if not child.readable:
                # All children must be readable.
                return False

        return True

    @property
    def writable(self) -> bool:
        """Returns ture if writable property, otherwise false."""
        for child in self._children:
            if not child.writable:
                # All children must be writable.
                return False

        return True

    def _retrieve_range(self) -> Range | None:
        """Retrieve a range type of data from the given profile."""
        # Range not applicatble for combinded property.
        return None

    def _retrieve_options(self) -> list[str] | None:
        """Retrieve a list of options from the given profile."""
        # Options not applicatble for combinded property.
        return None

    def _get_value(self, key_for_dict_value: str) -> Any:
        """Get the value from the api and update unit internally."""
        values: list[str] = []
        for child in self._children:
            values.append(child.get_value(self.key))

        _LOGGER.debug("%s get_value: %s", self.tag, values)
        return values

    def __str__(self) -> str:
        """Returns a string expression."""
        children_names: list[str] = [child.key for child in self._children]
        return f"{super().__str__()} {children_names}"


class SelectiveProperty(Property):
    """A property that operates by selecting one of several properties."""

    @property
    def range(self) -> Range | None:
        """Returns the range if exist."""
        if self._children:
            return self._children[0].range

        return super().range

    @property
    def options(self) -> list[str] | None:
        """Returns the options if exist."""
        if self._children:
            return self._children[0].options

        return super().options

    @property
    def unit(self) -> str | None:
        """Returns the unit if exist."""
        if self._children:
            return self._children[0].unit

        return self._unit

    @property
    def readable(self) -> bool:
        """Returns ture if readable property, otherwise false."""
        if self._children:
            return self._children[0].readable

        return super().readable

    @property
    def writable(self) -> bool:
        """Returns ture if writable property, otherwise false."""
        if self._children:
            return self._children[0].writable

        return super().writable

    def _get_value(self, key_for_dict_value: str) -> Any:
        """Get the value from the api and update unit internally."""

        # Iterates over the children to find one which has a value.
        if self._children:
            for _ in range(len(self._children)):
                value = self._children[0].get_value(self.key)
                if value is not None:
                    return value

                self._children.rotate(-1)

            return None

        return super()._get_value(self.key)

    async def _async_post_value(self, value: Any) -> None:
        """Post the value."""
        if self._children:
            return await self._children[0].async_post_value(value)
        else:
            return await super()._async_post_value(value)

    def __str__(self) -> str:
        """Returns a string expression."""
        children_names: list[str] = [child.key for child in self._children]
        return f"{super().__str__()} {children_names}"


# A type map for creating property.
PROPERTY_MODE_TYPE_MAP: dict[PropertyMode, type[Property]] = {
    PropertyMode.COMBINED: CombinedProperty,
    PropertyMode.SELECTIVE: SelectiveProperty,
}


def create_properties(
    device: LGDevice, info: PropertyInfo, platform: Platform
) -> list[Property] | None:
    """A helper method to create properties."""
    try:
        profiles = device.get_profiles(info.key)

        # If mode is combined or selective, the parent property can be
        # an empty property. In this case, create virtual profiles only
        # contains location informations from the first child.
        if not profiles and info.children and len(info.children) > 0:
            child_profiles = device.get_profiles(info.children[0].key)
            profiles = {location: None for location in child_profiles.keys()}

        if not profiles:
            raise RuntimeError(f"No profile. {info.key}")

        # Create properties.
        properties = [
            create_property(device, info, platform, profile, location)
            for location, profile in profiles.items()
            if validate_platform_creation(info, platform, profile)
        ]

        # Filter out invalid properties.
        # A property must have its own profile or at least one child.
        properties = list(
            filter(lambda p: p.profile or p.has_child, properties)
        )

        _LOGGER.debug(
            "[%s] Creating properties: [%s]",
            device.name,
            ",".join(map(str, properties)),
        )
        return properties
    except RuntimeError as e:
        _LOGGER.debug(
            "[%s] Failed to create properties: %s, %s",
            device.name,
            info.key,
            e,
        )
        return None


def fill_property_from_children(
    device: LGDevice,
    info: PropertyInfo,
    platform: Platform,
    property: Property,
    location: str,
) -> None:
    for child_info in info.children:
        child_profile = device.get_profile(location, child_info.key)
        if not validate_platform_creation(child_info, platform, child_profile):
            # The Combined property requires all children to be valid.
            if info.mode == PropertyMode.COMBINED:
                raise RuntimeError(f"No child profile. {child_info.key}")

            continue

        child_property = create_property(
            device, child_info, platform, child_profile, location
        )

        if child_info.feature is not None:
            property.add_feature(child_info.feature, child_property)
        else:
            property.add_child(child_property)


def create_property(
    device: LGDevice,
    info: PropertyInfo,
    platform: Platform,
    profile: Profile,
    location: str,
) -> Property:
    """Create a property."""
    constructor = PROPERTY_MODE_TYPE_MAP.get(info.mode, Property)
    property = constructor(device, info, profile=profile, location=location)

    # Try to create childeren properties.
    if info.children:
        fill_property_from_children(device, info, platform, property, location)

    # Try to create an unit provider property.
    if info.unit_info:
        unit_profile = device.get_profile(location, info.unit_info.key)
        if unit_profile:
            property.set_unit_provider(
                Property(
                    device,
                    info.unit_info,
                    profile=unit_profile,
                    location=location,
                )
            )

    return property


def validate_platform_creation(
    info: PropertyInfo, platform: Platform, profile: Profile
) -> bool:
    """Validate whether property can be created for the platform."""
    if not profile:
        # Allow creation for the type which has children.
        return info.mode != PropertyMode.DEFAULT

    readable: bool = profile.get(PROPERTY_READABLE, False)
    writable: bool = profile.get(PROPERTY_WRITABLE, False)

    # If an alternative method is exist, use it.
    if info.alt_validate_creation:
        return info.alt_validate_creation(readable, writable)

    # A property must have at least one mode: read or write.
    if not readable and not writable:
        return False

    if (
        platform == Platform.SELECT
        or platform == Platform.NUMBER
        or platform == Platform.SWITCH
    ):
        return writable
    elif (
        platform == Platform.SENSOR
        or platform == Platform.BINARY_SENSOR
        or platform == Platform.EVENT
    ):
        return readable and not writable

    # It is hard to validate for complex type of platform, so pass it.
    return True
