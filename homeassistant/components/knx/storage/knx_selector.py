"""Selectors for KNX."""

from collections.abc import Hashable, Iterable
from enum import Enum
from typing import Any

import voluptuous as vol

from ..validation import ga_validator, maybe_ga_validator, sync_state_validator
from .const import CONF_DPT, CONF_GA_PASSIVE, CONF_GA_STATE, CONF_GA_WRITE
from .util import dpt_string_to_dict


class AllSerializeFirst(vol.All):
    """Use the first validated value for serialization.

    This is a version of vol.All with custom error handling to
    show proper invalid markers for sub-schema items in the UI.
    """


class KNXSelectorBase:
    """Base class for KNX selectors supporting optional nested schemas."""

    schema: vol.Schema | vol.Any | vol.All
    selector_type: str
    # mark if self.schema should be serialized to `schema` key
    serialize_subschema: bool = False

    def __call__(self, data: Any) -> Any:
        """Validate the passed data."""
        return self.schema(data)

    def serialize(self) -> dict[str, Any]:
        """Serialize the selector to a dictionary."""
        # don't use "name", "default", "optional" or "required" in base output
        # as it will be overwritten by the parent keys attributes
        # "schema" will be overwritten by knx serializer if `self.serialize_subschema` is True
        raise NotImplementedError("Subclasses must implement this method.")


class KNXSectionFlat(KNXSelectorBase):
    """Generate a schema-neutral section with title and description for the following siblings."""

    selector_type = "knx_section_flat"
    schema = vol.Schema(None)

    def __init__(
        self,
        collapsible: bool = False,
    ) -> None:
        """Initialize the section."""
        self.collapsible = collapsible

    def serialize(self) -> dict[str, Any]:
        """Serialize the selector to a dictionary."""
        return {
            "type": self.selector_type,
            "collapsible": self.collapsible,
        }


class KNXSection(KNXSelectorBase):
    """Configuration groups similar to DataEntryFlow sections but with more options."""

    selector_type = "knx_section"
    serialize_subschema = True

    def __init__(
        self,
        schema: dict[str | vol.Marker, vol.Schemable],
        collapsible: bool = True,
    ) -> None:
        """Initialize the section."""
        self.collapsible = collapsible
        self.schema = vol.Schema(schema)

    def serialize(self) -> dict[str, Any]:
        """Serialize the section to a dictionary."""
        return {
            "type": self.selector_type,
            "collapsible": self.collapsible,
        }


class GroupSelectOption(KNXSelectorBase):
    """Schema for group select options."""

    selector_type = "knx_group_select_option"
    serialize_subschema: bool = True

    def __init__(self, schema: vol.Schemable, translation_key: str) -> None:
        """Initialize the group select option schema."""
        self.translation_key = translation_key
        self.schema = vol.Schema(schema)

    def serialize(self) -> dict[str, Any]:
        """Serialize the group select option to a dictionary."""
        return {
            "type": self.selector_type,
            "translation_key": self.translation_key,
        }


class GroupSelectSchema(vol.Any):
    """Use the first validated value.

    This is a version of vol.Any with custom error handling to
    show proper invalid markers for sub-schema items in the UI.
    """

    def _exec(self, funcs: Iterable, v: Any, path: list[Hashable] | None = None) -> Any:
        """Execute the validation functions."""
        errors: list[vol.Invalid] = []
        for func in funcs:
            try:
                if path is None:
                    return func(v)
                return func(path, v)
            except vol.Invalid as e:
                errors.append(e)
        if errors:
            raise next(
                (err for err in errors if "extra keys not allowed" not in err.msg),
                errors[0],
            )
        raise vol.AnyInvalid(self.msg or "no valid value found", path=path)


class GroupSelect(KNXSelectorBase):
    """Selector for group select options."""

    selector_type = "knx_group_select"
    serialize_subschema = True

    def __init__(
        self,
        *options: GroupSelectOption,
        collapsible: bool = True,
    ) -> None:
        """Initialize the group select selector."""
        self.collapsible = collapsible
        self.schema = GroupSelectSchema(*options)

    def serialize(self) -> dict[str, Any]:
        """Serialize the group select to a dictionary."""
        return {
            "type": self.selector_type,
            "collapsible": self.collapsible,
        }


class GASelector(KNXSelectorBase):
    """Selector for a KNX group address structure."""

    selector_type = "knx_group_address"

    def __init__(
        self,
        write: bool = True,
        state: bool = True,
        passive: bool = True,
        write_required: bool = False,
        state_required: bool = False,
        dpt: type[Enum] | None = None,
        valid_dpt: str | Iterable[str] | None = None,
    ) -> None:
        """Initialize the group address selector."""
        self.write = write
        self.state = state
        self.passive = passive
        self.write_required = write_required
        self.state_required = state_required
        self.dpt = dpt
        # valid_dpt is used in frontend to filter dropdown menu - no validation is done
        self.valid_dpt = (valid_dpt,) if isinstance(valid_dpt, str) else valid_dpt

        self.schema = self.build_schema()

    def serialize(self) -> dict[str, Any]:
        """Serialize the selector to a dictionary."""

        options: dict[str, Any] = {
            "write": {"required": self.write_required} if self.write else False,
            "state": {"required": self.state_required} if self.state else False,
            "passive": self.passive,
        }
        if self.dpt is not None:
            options["dptSelect"] = [
                {
                    "value": item.value,
                    "translation_key": item.value.replace(".", "_"),
                    "dpt": dpt_string_to_dict(item.value),  # used for filtering GAs
                }
                for item in self.dpt
            ]
        if self.valid_dpt is not None:
            options["validDPTs"] = [dpt_string_to_dict(dpt) for dpt in self.valid_dpt]

        return {
            "type": self.selector_type,
            "options": options,
        }

    def build_schema(self) -> vol.Schema:
        """Create the schema based on configuration."""
        schema: dict[vol.Marker, Any] = {}  # will be modified in-place
        self._add_group_addresses(schema)
        self._add_passive(schema)
        self._add_dpt(schema)
        return vol.Schema(
            vol.All(
                schema,
                vol.Schema(  # one group address shall be included
                    vol.Any(
                        {vol.Required(CONF_GA_WRITE): vol.IsTrue()},
                        {vol.Required(CONF_GA_STATE): vol.IsTrue()},
                        {vol.Required(CONF_GA_PASSIVE): vol.IsTrue()},
                        msg="At least one group address must be set",
                    ),
                    extra=vol.ALLOW_EXTRA,
                ),
            )
        )

    def _add_group_addresses(self, schema: dict[vol.Marker, Any]) -> None:
        """Add basic group address items to the schema."""

        def add_ga_item(key: str, allowed: bool, required: bool) -> None:
            """Add a group address item validator to the schema."""
            if not allowed:
                schema[vol.Remove(key)] = object
                return
            if required:
                schema[vol.Required(key)] = ga_validator
            else:
                schema[vol.Optional(key, default=None)] = maybe_ga_validator

        add_ga_item(CONF_GA_WRITE, self.write, self.write_required)
        add_ga_item(CONF_GA_STATE, self.state, self.state_required)

    def _add_passive(self, schema: dict[vol.Marker, Any]) -> None:
        """Add passive group addresses validator to the schema."""
        if self.passive:
            schema[vol.Optional(CONF_GA_PASSIVE, default=list)] = vol.Any(
                [ga_validator],
                vol.All(  # Coerce `None` to an empty list if passive is allowed
                    vol.IsFalse(), vol.SetTo(list)
                ),
            )
        else:
            schema[vol.Remove(CONF_GA_PASSIVE)] = object

    def _add_dpt(self, schema: dict[vol.Marker, Any]) -> None:
        """Add DPT validator to the schema."""
        if self.dpt is not None:
            schema[vol.Required(CONF_DPT)] = vol.In({item.value for item in self.dpt})
        else:
            schema[vol.Remove(CONF_DPT)] = object


class SyncStateSelector(KNXSelectorBase):
    """Selector for knx sync state validation."""

    schema = vol.Schema(sync_state_validator)
    selector_type = "knx_sync_state"

    def __init__(self, allow_false: bool = False) -> None:
        """Initialize the sync state validator."""
        self.allow_false = allow_false

    def serialize(self) -> dict[str, Any]:
        """Serialize the selector to a dictionary."""
        return {
            "type": self.selector_type,
            "allow_false": self.allow_false,
        }

    def __call__(self, data: Any) -> Any:
        """Validate the passed data."""
        if not self.allow_false and not data:
            raise vol.Invalid(f"Sync state cannot be {data}")
        return self.schema(data)
