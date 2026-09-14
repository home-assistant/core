"""Selectors for KNX."""

from collections.abc import Iterable
from enum import Enum
from typing import Any, override

import probatio

from homeassistant.const import CONF_PAYLOAD

from ..const import CONF_PAYLOAD_LENGTH, CONF_VALUE, SelectConf
from ..dpt import HaDptClass, get_supported_dpts
from ..validation import ga_validator, maybe_ga_validator, sync_state_validator
from .const import CONF_DPT, CONF_GA_PASSIVE, CONF_GA_STATE, CONF_GA_WRITE
from .util import dpt_string_to_dict


class AllSerializeFirst(probatio.All):
    """Use the first validated value for serialization.

    This is a version of probatio.All with custom error handling to
    show proper invalid markers for sub-schema items in the UI.
    """


class KNXSelectorBase:
    """Base class for KNX selectors supporting optional nested schemas."""

    schema: probatio.Schema | probatio.Any | probatio.All | GroupSelectSchema
    selector_type: str
    # mark if self.schema should be serialized to `schema` key
    serialize_subschema: bool = False

    def __call__(self, data: Any) -> Any:
        """Validate the passed data."""
        return self.schema(data)

    def serialize(self) -> dict[str, Any]:
        """Serialize the selector to a dictionary."""
        # don't use "name", "default", "optional" or
        # "required" in base output as it will be
        # overwritten by the parent keys attributes
        # "schema" will be overwritten by knx serializer
        # if `self.serialize_subschema` is True
        raise NotImplementedError("Subclasses must implement this method.")


class KNXSectionFlat(KNXSelectorBase):
    """Generate a schema-neutral section with title and description."""

    selector_type = "knx_section_flat"
    schema = probatio.Schema(None)

    def __init__(
        self,
        collapsible: bool = False,
    ) -> None:
        """Initialize the section."""
        self.collapsible = collapsible

    @override
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
        schema: dict[str | probatio.Marker, probatio.Schemable],
        collapsible: bool = True,
    ) -> None:
        """Initialize the section."""
        self.collapsible = collapsible
        self.schema = probatio.Schema(schema)

    @override
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

    def __init__(self, schema: probatio.Schemable, translation_key: str) -> None:
        """Initialize the group select option schema."""
        self.translation_key = translation_key
        self.schema = probatio.Schema(schema)

    @override
    def serialize(self) -> dict[str, Any]:
        """Serialize the group select option to a dictionary."""
        return {
            "type": self.selector_type,
            "translation_key": self.translation_key,
        }


def _has_extra_keys_error(exc: probatio.Invalid) -> bool:
    """Check if any of the errors is about extra keys."""
    errors = exc.errors if isinstance(exc, probatio.MultipleInvalid) else [exc]
    return any(isinstance(error, probatio.ExtraKeysInvalid) for error in errors)


class GroupSelectSchema:
    """Use the first validated value, like ``probatio.Any``.

    A standalone validator rather than a ``probatio.Any`` subclass, so it does not
    reach into validation-engine internals. On total failure it raises the most
    useful branch error (the first that is not an unknown-key error, else the
    first) so the UI marks a real problem instead of an extra key.
    """

    def __init__(self, *options: probatio.Schemable, msg: str | None = None) -> None:
        """Store the options to try in order."""
        self.validators = options
        self.msg = msg
        self._compiled = [probatio.Schema(option) for option in options]

    def __call__(self, data: Any) -> Any:
        """Return the first option that validates, else raise the best error."""
        errors: list[probatio.Invalid] = []
        for option in self._compiled:
            try:
                return option(data)
            except probatio.Invalid as err:
                errors.append(err)
        if errors:
            # an option is only reported when it matches the given keys;
            # `code` of a MultipleInvalid is just its first errors code, so
            # every error of an option is checked for being about extra keys
            raise next(
                (err for err in errors if not _has_extra_keys_error(err)),
                errors[0],
            )
        raise probatio.AnyInvalid(self.msg or "no valid value found")


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

    @override
    def serialize(self) -> dict[str, Any]:
        """Serialize the group select to a dictionary."""
        return {
            "type": self.selector_type,
            "collapsible": self.collapsible,
        }


class GASelector(KNXSelectorBase):
    """Selector for a KNX group address structure.

    `dpt_required` optional dpt only apply to dpt-class lists, enums are always required.
    `valid_dpt` is used in frontend to filter dropdown menu - no validation is done.
    """

    selector_type = "knx_group_address"

    def __init__(
        self,
        write: bool = True,
        state: bool = True,
        passive: bool = True,
        write_required: bool = False,
        state_required: bool = False,
        dpt: type[Enum] | list[HaDptClass] | None = None,
        dpt_required: bool = True,
        valid_dpt: str | Iterable[str] | None = None,
    ) -> None:
        """Initialize the group address selector."""
        self.write = write
        self.state = state
        self.passive = passive
        self.write_required = write_required
        self.state_required = state_required
        self.dpt = dpt
        self.dpt_required = dpt_required
        self.valid_dpt = (valid_dpt,) if isinstance(valid_dpt, str) else valid_dpt

        self.schema = self.build_schema()

    @override
    def serialize(self) -> dict[str, Any]:
        """Serialize the selector to a dictionary."""

        options: dict[str, Any] = {
            "write": {"required": self.write_required} if self.write else False,
            "state": {"required": self.state_required} if self.state else False,
            "passive": self.passive,
        }
        if self.dpt is not None:
            if isinstance(self.dpt, list):
                # optional / required is not passed to FE - only validated in BE
                options["dptClasses"] = self.dpt
            else:
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

    def build_schema(self) -> probatio.Schema:
        """Create the schema based on configuration."""
        schema: dict[probatio.Marker, Any] = {}  # will be modified in-place
        self._add_group_addresses(schema)
        self._add_passive(schema)
        self._add_dpt(schema)
        return probatio.Schema(
            probatio.All(
                schema,
                probatio.Schema(  # one group address shall be included
                    probatio.Any(
                        {probatio.Required(CONF_GA_WRITE): probatio.IsTrue()},
                        {probatio.Required(CONF_GA_STATE): probatio.IsTrue()},
                        {probatio.Required(CONF_GA_PASSIVE): probatio.IsTrue()},
                        msg="At least one group address must be set",
                    ),
                    extra=probatio.ALLOW_EXTRA,
                ),
            )
        )

    def _add_group_addresses(self, schema: dict[probatio.Marker, Any]) -> None:
        """Add basic group address items to the schema."""

        def add_ga_item(key: str, allowed: bool, required: bool) -> None:
            """Add a group address item validator to the schema."""
            if not allowed:
                schema[probatio.Remove(key)] = object
                return
            if required:
                schema[probatio.Required(key)] = ga_validator
            else:
                schema[probatio.Optional(key, default=None)] = maybe_ga_validator

        add_ga_item(CONF_GA_WRITE, self.write, self.write_required)
        add_ga_item(CONF_GA_STATE, self.state, self.state_required)

    def _add_passive(self, schema: dict[probatio.Marker, Any]) -> None:
        """Add passive group addresses validator to the schema."""
        if self.passive:
            schema[probatio.Optional(CONF_GA_PASSIVE, default=list)] = probatio.Any(
                [ga_validator],
                probatio.All(  # Coerce `None` to an empty list if passive is allowed
                    probatio.IsFalse(), probatio.SetTo(list)
                ),
            )
        else:
            schema[probatio.Remove(CONF_GA_PASSIVE)] = object

    def _add_dpt(self, schema: dict[probatio.Marker, Any]) -> None:
        """Add DPT validator to the schema."""
        if self.dpt is not None:
            if isinstance(self.dpt, list):
                marker = probatio.Required if self.dpt_required else probatio.Optional
                schema[marker(CONF_DPT)] = probatio.In(get_supported_dpts())
            else:
                schema[probatio.Required(CONF_DPT)] = probatio.In(
                    {item.value for item in self.dpt}
                )
        else:
            schema[probatio.Remove(CONF_DPT)] = object


class SyncStateSelector(KNXSelectorBase):
    """Selector for knx sync state validation."""

    schema = probatio.Schema(sync_state_validator)
    selector_type = "knx_sync_state"

    def __init__(self, allow_false: bool = False) -> None:
        """Initialize the sync state validator."""
        self.allow_false = allow_false

    @override
    def serialize(self) -> dict[str, Any]:
        """Serialize the selector to a dictionary."""
        return {
            "type": self.selector_type,
            "allow_false": self.allow_false,
        }

    @override
    def __call__(self, data: Any) -> Any:
        """Validate the passed data."""
        if not self.allow_false and not data:
            raise probatio.Invalid(f"Sync state cannot be {data}")
        return self.schema(data)


class KnxPayloadSelector(KNXSelectorBase):
    """Selector for KNX payload configuration.

    Raw payloads are stored as hex strings.
    """

    schema = probatio.Any(
        {
            probatio.Required(CONF_VALUE): object,
        },
        {
            probatio.Required(CONF_PAYLOAD): str,
            probatio.Required(CONF_PAYLOAD_LENGTH): probatio.All(
                int, probatio.Range(min=0, max=14)
            ),
        },
    )
    selector_type = "knx_payload"

    def __init__(self, ga_path: str) -> None:
        """Initialize the KNX payload selector."""
        self.ga_path = ga_path

    @override
    def serialize(self) -> dict[str, Any]:
        """Serialize the selector to a dictionary."""
        return {
            "type": self.selector_type,
            "ga_path": self.ga_path,
        }

    @override
    def __call__(self, data: Any) -> Any:
        """Validate the passed data."""
        validated = self.schema(data)
        if CONF_PAYLOAD in validated and CONF_PAYLOAD_LENGTH in validated:
            payload = validated[CONF_PAYLOAD]
            payload_length = validated[CONF_PAYLOAD_LENGTH]
            try:
                int_payload = int(payload, 16)
            except ValueError as ex:
                raise probatio.Invalid(f"Invalid payload format: {payload}") from ex
            validated[CONF_PAYLOAD] = hex(int_payload)  # prepends "0x" if not present

            if int_payload < 0:
                raise probatio.Invalid(f"Payload cannot be negative: {payload}")
            if payload_length == 0:
                # DPT 1,2,3 is marked length 0, has 6 bit size
                if int_payload > 63:
                    raise probatio.Invalid(
                        f"Payload exceeds DPT 1,2,3 limit of 0x3f (63): {payload}"
                    )
            else:
                max_payload = (1 << (payload_length * 8)) - 1
                if int_payload > max_payload:
                    raise probatio.Invalid(
                        f"Payload {payload} exceeds possible maximum for "
                        f"length {payload_length}: {hex(max_payload)}"
                    )
        # CONF_VALUE branch needs subvalidator as we don't have the DPT available here
        return validated


class KnxSelectOptionsSelector(KNXSelectorBase):
    """Selector for a list of select options mapping names to payloads.

    Each option pairs a name with a payload following the `KnxPayloadSelector`
    contract (a typed `value` or a raw `payload` + `payload_length`), resolved
    against the linked group address's DPT via `ga_path`.
    """

    selector_type = "knx_select_options"

    def __init__(self, ga_path: str) -> None:
        """Initialize the options selector."""
        self.ga_path = ga_path
        self._payload_selector = KnxPayloadSelector(ga_path=ga_path)
        self.schema = probatio.Schema([self._validate_option])

    @override
    def serialize(self) -> dict[str, Any]:
        """Serialize the selector to a dictionary."""
        return {
            "type": self.selector_type,
            "ga_path": self.ga_path,
        }

    def _validate_option(self, data: Any) -> dict[str, Any]:
        """Validate a single option entry.

        The typed `value` branch needs the DPT and is validated by the platform
        sub-validator.
        """
        if not isinstance(data, dict):
            raise probatio.Invalid("Each option must be a dictionary")
        option = data.get(SelectConf.OPTION)
        if not isinstance(option, str) or not option:
            raise probatio.Invalid("Option name is required", path=[SelectConf.OPTION])
        payload = {
            key: value for key, value in data.items() if key != SelectConf.OPTION
        }
        validated = self._payload_selector(payload)
        return {SelectConf.OPTION: option, **validated}
