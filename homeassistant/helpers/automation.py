"""Helpers for automation."""

from collections.abc import Callable, Coroutine, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
import functools
import inspect
from typing import Any, Final, Protocol, Self

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    callback,
    split_entity_id,
)

from .entity import get_device_class_or_undefined
from .typing import UNDEFINED, ConfigType, UndefinedType

CONF_UNIT: Final = "unit"


class AnyDeviceClassType(Enum):
    """Singleton type for matching any device class."""

    _singleton = 0


ANY_DEVICE_CLASS = AnyDeviceClassType._singleton  # noqa: SLF001


@dataclass(frozen=True, slots=True)
class DomainSpec:
    """Describes how to match and extract a value from an entity.

    Used by triggers and conditions.
    """

    device_class: str | AnyDeviceClassType | None = ANY_DEVICE_CLASS
    value_source: str | None = None
    """Attribute name to extract the value from, or None for state.state."""


def filter_by_domain_specs(
    hass: HomeAssistant,
    domain_specs: Mapping[str, DomainSpec],
    entities: set[str],
) -> set[str]:
    """Filter entities matching any of the domain specs."""
    result: set[str] = set()
    for entity_id in entities:
        if not (domain_spec := domain_specs.get(split_entity_id(entity_id)[0])):
            continue
        if (
            domain_spec.device_class is not ANY_DEVICE_CLASS
            and get_device_class_or_undefined(hass, entity_id)
            != domain_spec.device_class
        ):
            continue
        result.add(entity_id)
    return result


def get_absolute_description_key(domain: str, key: str) -> str:
    """Return the absolute description key."""
    if not key.startswith("_"):
        return f"{domain}.{key}"
    key = key[1:]  # Remove leading underscore
    if not key:
        return domain
    return key


def get_relative_description_key(domain: str, key: str) -> str:
    """Return the relative description key."""
    platform, *subtype = key.split(".", 1)
    if platform != domain:
        return f"_{key}"
    if not subtype:
        return "_"
    return subtype[0]


def move_top_level_schema_fields_to_options(
    config: ConfigType, options_schema_dict: dict[vol.Marker, Any]
) -> ConfigType:
    """Move top-level fields to options.

    This function is used to help migrating old-style configs to new-style configs
    for triggers and conditions.
    If options is already present, the config is returned as-is.
    """
    if CONF_OPTIONS in config:
        return config

    config = config.copy()
    options = config.setdefault(CONF_OPTIONS, {})

    # Move top-level fields to options
    for key_marked in options_schema_dict:
        key = key_marked.schema
        if key in config:
            options[key] = config.pop(key)

    return config


def move_options_fields_to_top_level(
    config: ConfigType, base_schema: vol.Schema
) -> ConfigType:
    """Move options fields to top-level.

    This function is used to provide backwards compatibility for new-style configs
    for triggers and conditions.

    The config is returned as-is, if any of the following is true:
    - options is not present
    - options is not a dict
    - the config with options field removed fails the base_schema validation (most
    likely due to additional keys being present)

    Those conditions are checked to make it so that only configs that have the structure
    of the new-style are modified, whereas valid old-style configs are preserved.
    """
    options = config.get(CONF_OPTIONS)

    if not isinstance(options, dict):
        return config

    new_config: ConfigType = config.copy()
    new_config.pop(CONF_OPTIONS)

    try:
        new_config = base_schema(new_config)
    except vol.Invalid:
        return config

    new_config.update(options)

    return new_config


@dataclass(frozen=True, kw_only=True)
class ThresholdConfig:
    """Configuration for threshold conditions and triggers."""

    numerical: bool
    entity: str | None
    number: float | None
    unit: str | UndefinedType | None

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> Self | None:
        """Create ThresholdConfig from config dict."""
        if config is None:
            return None

        entity: str | None = None
        number: float | None = None
        unit: str | UndefinedType | None = UNDEFINED
        numerical = "number" in config
        if numerical:
            number = config["number"]
            unit = config.get("unit_of_measurement", UNDEFINED)
        else:
            entity = config["entity"]

        return cls(numerical=numerical, number=number, entity=entity, unit=unit)


@dataclass(slots=True, frozen=True, kw_only=True)
class ValidationFinding:
    """A non-fatal problem detected while validating a trigger, condition or action config.

    A validator reports findings through the optional ``issue_reporter`` passed to config
    validation (e.g. ``async_validate_trigger_config``). The validator does not know which
    automation, script or template entity owns the config; the code that initiated the
    validation adds that owner context and materializes a repair issue via
    ``async_create_validation_issue``.

    ``finding_type`` is the base translation key of the repair issue - its strings live in
    the ``homeassistant`` integration, which the issue is filed under. ``issue_key``
    discriminates findings of the same type within one owner (e.g. the offending device
    id). ``placeholders`` are the finding-specific translation placeholders.
    """

    finding_type: str
    issue_key: str
    placeholders: Mapping[str, str]


class ValidationIssueReporter(Protocol):
    """Reports a non-fatal problem found while validating a config."""

    @callback
    def __call__(self, finding: ValidationFinding, /) -> None:
        """Report a validation finding."""


@functools.cache
def _validator_accepts_issue_reporter(validator: Callable[..., Any]) -> bool:
    """Return True if a platform validator opts in to an ``issue_reporter``."""
    try:
        return "issue_reporter" in inspect.signature(validator).parameters
    except TypeError, ValueError:
        return False


async def async_call_platform_validator(
    validator: Callable[..., ConfigType | Coroutine[Any, Any, ConfigType]],
    hass: HomeAssistant,
    conf: ConfigType,
    issue_reporter: ValidationIssueReporter | None,
) -> ConfigType:
    """Call a platform config validator, making the ``issue_reporter`` opt-in.

    This helper exists solely so ``issue_reporter`` can be an optional parameter of
    platform validators: the reporter is forwarded only to validators that declare it,
    leaving legacy two-argument validators (including those in custom integrations)
    called unchanged. The validator may be a coroutine function or a plain function.
    """
    if issue_reporter is not None and _validator_accepts_issue_reporter(validator):
        result = validator(hass, conf, issue_reporter=issue_reporter)
    else:
        result = validator(hass, conf)
    if isinstance(result, Coroutine):
        return await result
    return result


@callback
def async_create_validation_issue(
    hass: HomeAssistant,
    finding: ValidationFinding,
    *,
    issue_domain: str,
    owner_key: str,
    name: str,
    entity_id: str,
    edit_url: str | None,
) -> str:
    """Materialize a repair issue for a validation finding.

    Returns the created issue id.
    """
    from .issue_registry import IssueSeverity, async_create_issue  # noqa: PLC0415

    issue_id = f"{issue_domain}_{finding.finding_type}_{owner_key}_{finding.issue_key}"
    placeholders = {"name": name, "entity_id": entity_id, **finding.placeholders}
    if edit_url is not None:
        translation_key = finding.finding_type
        placeholders["edit"] = edit_url
    else:
        translation_key = f"{finding.finding_type}_no_edit"
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        issue_id,
        is_fixable=False,
        issue_domain=issue_domain,
        severity=IssueSeverity.ERROR,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )
    return issue_id


@callback
def async_clear_validation_issues(
    hass: HomeAssistant, issue_ids: Iterable[str]
) -> None:
    """Delete repair issues previously created from validation findings."""
    from .issue_registry import async_delete_issue  # noqa: PLC0415

    for issue_id in issue_ids:
        async_delete_issue(hass, HOMEASSISTANT_DOMAIN, issue_id)
