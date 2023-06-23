# pylint: skip-file
"""Utilities for managing the GraphQL schema."""

from __future__ import annotations

from collections import namedtuple
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from typing import Union, get_args, get_origin, get_type_hints

from apischema import deserialize as _deserialize
from apischema.metadata.keys import CONVERSION_METADATA, SKIP_METADATA
from apischema.utils import to_camel_case
from gql.dsl import DSLField, DSLInlineFragment, DSLSchema

# For compatibility with < python 3.10.
NoneType = type(None)


def deserialize(*args, **kwargs):
    """Deserialize a GraphQL JSON blob.

    :meta private:
    """
    kwargs.setdefault("aliaser", to_camel_case)
    return _deserialize(*args, **kwargs)


_Field = namedtuple("_Field", ["name", "types"])


def _fields(cls) -> Iterator[_Field]:
    """Return _Field objects for every field on the given dataclass.

    :meta private:
    """
    hints = get_type_hints(cls)
    for field in fields(cls):
        skip_md = field.metadata.get(SKIP_METADATA, None)
        if skip_md and (skip_md.serialization or skip_md.deserialization):
            continue

        conversion_md = field.metadata.get(CONVERSION_METADATA, None)
        if conversion_md:
            yield _Field(field.name, [conversion_md.deserialization.source])
            continue

        field_type = hints[field.name]
        origin = get_origin(field_type)

        if origin == Union:
            # Drop None from Optional fields.
            field_types = set(get_args(field_type)) - {NoneType}
            if len(field_types) == 1:
                [field_type] = field_types
            else:
                yield _Field(field.name, list(field_types))
                continue
        elif origin == list:
            # Extract the contained type.
            # We assume all list types are uniform.
            [field_type] = get_args(field_type)

        yield _Field(field.name, [field_type])


def get_selectors(data_schema: DSLSchema, cls: type) -> list[DSLField]:
    """Construct GraphQL selectors for the given dataclass.

    :meta private:
    """
    ret = []
    for field in _fields(cls):
        dsl_field = getattr(getattr(data_schema, cls.__name__), field.name)
        if len(field.types) == 1:
            [f_type] = field.types
            if is_dataclass(f_type):
                ret.append(
                    getattr(dsl_field, "select")(*get_selectors(data_schema, f_type))
                )
            else:
                ret.append(dsl_field)
        else:
            # This is a Union; we must pass an inline fragment for each type.
            sel_args = []
            for f_type in field.types:
                if not is_dataclass(f_type):
                    raise NotImplementedError
                sel_args.append(
                    DSLInlineFragment()
                    .on(getattr(data_schema, f_type.__name__))
                    .select(*get_selectors(data_schema, f_type))
                )
            ret.append(getattr(dsl_field, "select")(*sel_args))
    return ret
