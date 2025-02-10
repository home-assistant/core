"""Voluptuous UI schemas for the KNX integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Final, Protocol, Self, TypedDict, cast, runtime_checkable

import voluptuous as vol
from voluptuous_serialize import UNSUPPORTED, convert as vol_serializer_convert
from xknx.dpt import DPTBase
from xknx.exceptions import CouldNotParseAddress
from xknx.telegram import GroupAddress as XKnxGroupAddress
from xknx.telegram.address import parse_device_group_address

from homeassistant.const import (
    CONF_DESCRIPTION,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_TYPE,
    EntityCategory,
)
from homeassistant.helpers.typing import VolSchemaType

from .const import CONF_CONFIG, CONF_ITEMS, CONF_PROPERTIES
from .storage.const import (
    CONF_DEVICE_INFO,
    CONF_DPT,
    CONF_GA_PASSIVE,
    CONF_GA_STATE,
    CONF_GA_WRITE,
)


@runtime_checkable
class SerializableSchema(Protocol):
    """Protocol for serializing Voluptuous schema definitions.

    This Protocol defines a structure for classes that implement schema serialization.
    The `serialize` method allows the transformation of a Voluptuous schema definition
    into a JSON-serializable dictionary format. This is particularly useful for
    providing schema details to the frontend for dynamic form generation.

    Any class implementing this Protocol must provide a `serialize` method that:
      - Processes the class (`cls`) and an instance (`value`) of the same type.
      - Handles nested or complex schema definitions using a customizable `convert` function.
      - Returns a dictionary representation of the schema that adheres to JSON serialization rules.
    """

    def get_schema(self) -> VolSchemaType:
        """Retrieve the Voluptuous schema definition for the instance.

        This method returns the schema definition required for validation. Unlike a
        static method or property, `get_schema` is an instance method because the
        schema may depend on runtime parameters or dynamic calculations that are
        only available after initialization.

        Returns:
            VolSchemaType: The Voluptuous schema definition associated with the instance.

        """

    @classmethod
    def serialize(cls, value: Self, convert: Callable[[Any], Any]) -> dict[str, Any]:
        """Serialize a Voluptuous schema definition into a JSON-compatible dictionary.

        This method transforms an instance of the schema into a dictionary format
        that is ready for use in frontend applications or APIs. The `convert` parameter
        allows recursive handling of nested schemas or custom elements that require
        special processing.

        Args:
            cls (type[Self]): The schema class calling this method. This ensures
                type consistency between the schema class and the provided instance.
            value (Self): An instance of the schema class, containing the schema
                definition and any associated data.
            convert (Callable[[Any], Any]): A function to process nested or custom
                schema elements recursively. This ensures compatibility with complex
                or deeply nested schema structures.

        Returns:
            dict[str, Any]: A dictionary representation of the schema,
            ready for JSON serialization and suitable for frontend consumption.

        Raises:
            vol.Invalid: If the schema definition or its associated data is invalid
            or does not meet the required constraints.

        """


class DptUtils:
    """Utility class for working with KNX Datapoint Types (DPTs)."""

    @staticmethod
    def format_dpt(dpt: type[DPTBase]) -> str:
        """Generate a string representation of a DPT class.

        Args:
            dpt: A DPT class type.

        Returns:
            A formatted string representation of the DPT class, including both main
            and sub numbers (e.g., '1.002'). If the sub number is None, only the
            main number is included (e.g., '14').

        Raises:
            ValueError: If an invalid DPT class is provided

        """
        if not issubclass(dpt, DPTBase) or not dpt.has_distinct_dpt_numbers():
            raise ValueError("Invalid DPT class provided.")

        return (
            f"{dpt.dpt_main_number}.{dpt.dpt_sub_number:03}"
            if dpt.dpt_sub_number is not None
            else f"{dpt.dpt_main_number}"
        )

    @staticmethod
    @cache
    def derive_subtypes(*types: type[DPTBase]) -> tuple[type[DPTBase], ...]:
        """Extract all distinct DPT types derived from the given DPT classes.

        This function takes one or more DPT classes as input and recursively
        gathers all types that are derived from these classes.

        Args:
            types: One or more DPT classes to process.

        Returns:
            A tuple of all distinct DPTs found in the class tree of the provided classes.

        """
        return tuple(
            dpt
            for dpt_class in types
            for dpt in dpt_class.dpt_class_tree()
            if dpt.has_distinct_dpt_numbers()
        )


class ConfigGroupSchema(SerializableSchema):
    """Data entry flow section."""

    class UIOptions(TypedDict, total=False):
        """Represents the configuration for a ConfigGroup in the UI."""

        collapsible: bool  # Indicates whether the section can be collapsed by the user.

    UI_OPTIONS_SCHEMA: Final[vol.Schema] = vol.Schema(
        {vol.Optional("collapsible", default=False): bool}
    )

    def __init__(self, schema: vol.Schema, ui_options: UIOptions | None = None) -> None:
        """Initialize."""
        self.schema = schema
        self.ui_options: ConfigGroupSchema.UIOptions = self.UI_OPTIONS_SCHEMA(
            ui_options or {}
        )

    def __call__(self, value: Any) -> Any:
        """Validate value against schema."""
        return self.schema(value)

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls, value: ConfigGroupSchema, convert: Callable[[Any], Any]
    ) -> dict[str, Any]:
        """Convert Section schema into a dictionary representation."""

        return {
            CONF_TYPE: "config_group",
            "ui_options": {
                "collapsible": value.ui_options["collapsible"],
            },
            CONF_PROPERTIES: convert(value.schema),
        }


class GroupAddressSchema(SerializableSchema):
    """Voluptuous-compatible validator for a KNX group address."""

    def __init__(self, allow_internal_address: bool = True) -> None:
        """Initialize."""
        self.allow_internal_address = allow_internal_address

    def __call__(self, value: str | int | None) -> str | int | None:
        """Validate that the value is parsable as GroupAddress or InternalGroupAddress."""
        if not isinstance(value, (str, int)):
            raise vol.Invalid(
                f"'{value}' is not a valid KNX group address: Invalid type '{type(value).__name__}'"
            )
        try:
            if not self.allow_internal_address:
                XKnxGroupAddress(value)
            else:
                parse_device_group_address(value)

        except CouldNotParseAddress as exc:
            raise vol.Invalid(
                f"'{value}' is not a valid KNX group address: {exc.message}"
            ) from exc
        return value

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return vol.Schema(None)

    @classmethod
    def serialize(
        cls,
        value: GroupAddressSchema,
        convert: Callable[[vol.Schema], Any],
    ) -> dict[str, Any]:
        """Convert GroupAddress schema into a dictionary representation."""
        return {
            CONF_TYPE: "group_address",
            "allow_internal_address": value.allow_internal_address,
        }


class GroupAddressListSchema(SerializableSchema):
    """Voluptuous-compatible validator for a collection of KNX group addresses."""

    schema: vol.Schema

    def __init__(self, allow_internal_addresses: bool = True) -> None:
        """Initialize the group address collection."""
        self.allow_internal_addresses = allow_internal_addresses
        self.schema = self._build_schema()

    def __call__(self, value: Any) -> Any:
        """Validate the passed data."""
        return self.schema(value)

    def _build_schema(self) -> vol.Schema:
        """Create the schema based on configuration."""
        return vol.Schema(
            vol.Any(
                [
                    GroupAddressSchema(
                        allow_internal_address=self.allow_internal_addresses
                    )
                ],
                vol.All(  # Coerce `None` to an empty list if passive is allowed
                    vol.IsFalse(), vol.SetTo(list)
                ),
            )
        )

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls, value: GroupAddressListSchema, convert: Callable[[Any], Any]
    ) -> dict[str, Any]:
        """Convert GroupAddressCollection schema into a dictionary representation."""
        return {
            CONF_TYPE: "group_address_list",
            CONF_ITEMS: convert(
                GroupAddressSchema(
                    allow_internal_address=value.allow_internal_addresses
                )
            ),
        }


class SyncStateSchema(SerializableSchema):
    """Voluptuous-compatible validator for sync state selector."""

    schema: Final = vol.Any(
        vol.All(vol.Coerce(int), vol.Range(min=2, max=1440)),
        vol.Match(r"^(init|expire|every)( \d*)?$"),
        # Ensure that the value is a type boolean and not coerced to a boolean
        lambda v: v
        if isinstance(v, bool)
        else (_ for _ in ()).throw(vol.Invalid("Invalid value")),
    )

    def __call__(self, value: Any) -> Any:
        """Validate value against schema."""
        return self.schema(value)

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls, value: SyncStateSchema, convert: Callable[[Any], Any]
    ) -> dict[str, Any]:
        """Convert SyncState schema into a dictionary representation."""
        return {CONF_TYPE: "sync_state"}


@dataclass
class GroupAddressConfigSchema:
    """Voluptuous-compatible validator for the group address config."""

    allowed_dpts: tuple[type[DPTBase], ...]
    write: bool = True
    state: bool = True
    passive: bool = True
    write_required: bool = False
    state_required: bool = False
    schema: vol.Schema = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the group address selector."""
        self._validate_config()
        self.schema = self.build_schema()

    def _validate_config(self) -> None:
        """Validate the configuration parameters."""
        if len(self.allowed_dpts) == 0:
            raise ValueError("At least one allowed DPT must be provided.")
        if not self.write and not self.state:
            raise ValueError("At least one of 'write' or 'state' must be enabled.")
        if not self.write and self.write_required:
            raise ValueError("Write is required but not enabled.")
        if not self.state and self.state_required:
            raise ValueError("State is required but not enabled.")
        if not self.state and self.passive:
            raise ValueError(
                "Passive group addresses are only allowed for state addresses."
            )

    def __call__(self, data: Any) -> Any:
        """Validate the passed data."""

        # Ensure that at least one of 'write', 'state', or 'passive' is provided
        # when a DPT is specified. This constraint is not enforced in the schema
        # to work around compatibility issues with vol.All and the vol serializer.
        if CONF_DPT in data and not any(
            key in data for key in (CONF_GA_WRITE, CONF_GA_STATE, CONF_GA_PASSIVE)
        ):
            raise vol.Invalid(
                "At least one of 'write', 'state', or 'passive' must be provided when a DPT is specified."
            )
        return self.schema(data)

    def build_schema(self) -> vol.Schema:
        """Create the schema based on configuration."""
        schema: dict[vol.Marker, Any] = {}
        self._add_group_addresses(schema)
        self._add_passive(schema)
        self._add_dpt(schema)

        return vol.Schema(schema)

    def _add_group_addresses(self, schema: dict[vol.Marker, Any]) -> None:
        """Add basic group address items to the schema."""
        items = [
            (CONF_GA_WRITE, self.write, self.write_required),
            (CONF_GA_STATE, self.state, self.state_required),
        ]

        for key, allowed, required in items:
            if not allowed:
                schema[vol.Remove(key)] = object
            elif required:
                schema[vol.Required(key)] = GroupAddressSchema()
            else:
                schema[vol.Optional(key, default=None)] = vol.Maybe(
                    GroupAddressSchema()
                )

    def _add_passive(self, schema: dict[vol.Marker, Any]) -> None:
        """Add passive group addresses validator to the schema."""
        if self.passive:
            schema[vol.Optional(CONF_GA_PASSIVE, default=list)] = (
                GroupAddressListSchema()
            )
        else:
            schema[vol.Remove(CONF_GA_PASSIVE)] = None

    def _add_dpt(self, schema: dict[vol.Marker, Any]) -> None:
        """Add DPT validator to the schema."""
        schema[vol.Required(CONF_DPT)] = vol.All(
            str,
            vol.In([DptUtils.format_dpt(dpt) for dpt in self.allowed_dpts]),
        )

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls,
        value: GroupAddressConfigSchema,
        convert: Callable[[Any], Any],
    ) -> dict[str, Any]:
        """Convert GroupAddressConfig schema into a dictionary representation."""
        return {
            CONF_TYPE: "group_address_config",
            CONF_PROPERTIES: convert(value.schema),
        }


class EntityConfigGroupSchema(ConfigGroupSchema):
    """Voluptuous-compatible validator for the entity configuration group."""

    def __init__(
        self, allowed_categories: tuple[EntityCategory, ...] | None = None
    ) -> None:
        """Initialize the schema with optional allowed categories.

        :param allowed_categories: Tuple of allowed EntityCategory values.
        """

        allowed_categories = allowed_categories or tuple(EntityCategory)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                ): str,
                vol.Optional(
                    CONF_ENTITY_CATEGORY,
                    default=None,
                ): vol.Maybe(vol.In(allowed_categories)),
                vol.Optional(
                    CONF_DEVICE_INFO,
                    default=None,
                ): vol.Maybe(str),
            },
        )

        super().__init__(schema)


class PlatformConfigSchema(SerializableSchema):
    """Data entry flow section."""

    def __init__(
        self,
        platform: str,
        config_schema: vol.Schema,
    ) -> None:
        """Initialize."""
        self.schema = vol.Schema(
            {
                vol.Required(CONF_PLATFORM): platform,
                vol.Required(
                    CONF_CONFIG,
                ): ConfigGroupSchema(config_schema),
            }
        )

    def __call__(self, value: Any) -> dict[str, Any]:
        """Validate value against schema."""
        return cast(dict, self.schema(value))

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls, value: PlatformConfigSchema, convert: Callable[[Any], Any]
    ) -> dict[str, Any]:
        """Convert Section schema into a dictionary representation."""

        return {
            CONF_TYPE: "platform_config",
            CONF_PROPERTIES: convert(value.schema),
        }


class SchemaSerializer:
    """A utility class to serialize different KNX-related object types (e.g., GASelector or Section)."""

    _supported_types: tuple[type[SerializableSchema], ...] = (
        ConfigGroupSchema,
        GroupAddressConfigSchema,
        GroupAddressListSchema,
        GroupAddressSchema,
        PlatformConfigSchema,
        SyncStateSchema,
    )

    @classmethod
    def convert(cls, schema: Any) -> Any:
        """Convert a Voluptuous schema into a dictionary representation.

        This method utilizes a custom serializer to transform the given
        Voluptuous schema into a structured dictionary format.

        Args:
            schema (Any): A Voluptuous schema object to be converted.

        Returns:
            Any: A dictionary representing the converted schema.

        Raises:
            TypeError: If the input schema is not a valid Voluptuous schema.

        """
        return vol_serializer_convert(schema, custom_serializer=cls._serializer)

    @classmethod
    def _serializer(cls, value: Any) -> Any | object:
        """Determine how to serialize the given object based on its type.

        - If `value` is an instance of one of the types in `_supported_types`,
            the corresponding `serialize` method is called.
        - If `value` is a Mapping (e.g., a dictionary), it iterates over
            its items and creates a serialized list of key-value pairs.
        - If the type is not supported, `UNSUPPORTED` is returned.

        Args:
            value (Any): The object to be serialized (e.g., GASelector, Section, etc.).

        Returns:
            Any | object: A dictionary or list representing the serialized object.
                            Returns `UNSUPPORTED` if the type is not supported.

        Raises:
            TypeError: If the serialization process encounters an unexpected type.

        """
        # Check if `value` matches one of the supported types
        for supported_type in cls._supported_types:
            if isinstance(value, supported_type):
                # Call the appropriate serialize method
                return supported_type.serialize(value, cls.convert)

        # If `value` is a mapping (e.g., a dictionary), process its items.
        # This code overrides the default behavior of voluptuous-serialize
        # in order to handle the `vol.Remove` marker. The long-term goal is
        # to contribute this feature upstream so it can eventually be removed
        # from our local code.
        if isinstance(value, Mapping):
            serialized_items = []

            for key, child_value in value.items():
                # Skip entries if the key is of type vol.Remove
                if isinstance(key, vol.Remove):
                    continue

                description = None

                # If the key is a vol.Marker, extract schema and description
                if isinstance(key, vol.Marker):
                    param_name = key.schema
                    description = key.description
                else:
                    param_name = key

                # Convert the child value using the `convert` method
                serialized_value = cls.convert(child_value)
                serialized_value[CONF_NAME] = param_name

                # If there's a description, add it to the serialized output
                if description is not None:
                    serialized_value[CONF_DESCRIPTION] = description

                # Check if the key is Required or Optional
                if isinstance(key, (vol.Required, vol.Optional)):
                    key_type_name = key.__class__.__name__.lower()
                    serialized_value[key_type_name] = True

                    # If the default is defined and callable, call it
                    if key.default is not vol.UNDEFINED and callable(key.default):
                        serialized_value["default"] = key.default()

                serialized_items.append(serialized_value)

            return serialized_items

        # If no supported type found, return UNSUPPORTED
        return UNSUPPORTED
