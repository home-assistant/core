"""Custom serializer for KNX schemas."""

from typing import Any, cast

import voluptuous as vol
from voluptuous_serialize import UNSUPPORTED, UnsupportedType, convert

from homeassistant.const import Platform
from homeassistant.helpers import selector

from .entity_store_schema import KNX_SCHEMA_FOR_PLATFORM
from .knx_selector import AllSerializeFirst, GroupSelectSchema, KNXSelectorBase


def knx_serializer(
    schema: vol.Schema,
) -> dict[str, Any] | list[dict[str, Any]] | UnsupportedType:
    """Serialize KNX schema."""
    if isinstance(schema, GroupSelectSchema):
        return [
            cast(
                dict[str, Any],  # GroupSelectOption converts to a dict with subschema
                convert(option, custom_serializer=knx_serializer),
            )
            for option in schema.validators
        ]
    if isinstance(schema, KNXSelectorBase):
        result = schema.serialize()
        if schema.serialize_subschema:
            result["schema"] = convert(schema.schema, custom_serializer=knx_serializer)
        return result
    if isinstance(schema, AllSerializeFirst):
        return convert(schema.validators[0], custom_serializer=knx_serializer)

    if isinstance(schema, selector.Selector):
        return schema.serialize() | {"type": "ha_selector"}

    return UNSUPPORTED


def get_serialized_schema(
    platform: Platform,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Get the schema for a specific platform."""
    if knx_schema := KNX_SCHEMA_FOR_PLATFORM.get(platform):
        return convert(knx_schema, custom_serializer=knx_serializer)
    return None
