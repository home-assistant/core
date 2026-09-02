"""Validation utilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from awesomeversion import AwesomeVersion
from homeassistant.helpers.config_validation import url as url_validator
import voluptuous as vol

from ..const import LOCALE


@dataclass
class Validate:
    """Validate."""

    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return bool if the validation was a success."""
        return len(self.errors) == 0


def _country_validator(values) -> list[str]:
    """Custom country validator."""
    countries = []
    if isinstance(values, str):
        countries.append(values.upper())
    elif isinstance(values, list):
        for value in values:
            countries.append(value.upper())
    else:
        raise vol.Invalid(f"Value '{values}' is not a string or list.", path=["country"])

    for country in countries:
        if country not in LOCALE:
            raise vol.Invalid(f"Value '{country}' is not in {LOCALE}.", path=["country"])

    return countries


HACS_MANIFEST_JSON_SCHEMA = vol.Schema(
    {
        vol.Optional("content_in_root"): bool,
        vol.Optional("country"): _country_validator,
        vol.Optional("filename"): str,
        vol.Optional("hacs"): str,
        vol.Optional("hide_default_branch"): bool,
        vol.Optional("homeassistant"): str,
        vol.Optional("persistent_directory"): str,
        vol.Optional("render_readme"): bool,
        vol.Optional("zip_release"): bool,
        vol.Required("name"): str,
    },
    extra=vol.PREVENT_EXTRA,
)

INTEGRATION_MANIFEST_JSON_SCHEMA = vol.Schema(
    {
        vol.Required("codeowners"): list,
        vol.Required("documentation"): url_validator,
        vol.Required("domain"): str,
        vol.Required("issue_tracker"): url_validator,
        vol.Required("name"): str,
        vol.Required("version"): vol.Coerce(AwesomeVersion),
    },
    extra=vol.ALLOW_EXTRA,
)


def validate_repo_data(schema: dict[str, Any], extra: int) -> Callable[[Any], Any]:
    """Return a validator for repo data.

    This is used instead of vol.All to always try both the repo schema and
    and the validate_version validator.
    """
    _schema = vol.Schema(schema, extra=extra)

    def validate_repo_data(data: Any) -> Any:
        """Validate integration repo data."""
        schema_errors: vol.MultipleInvalid | None = None
        try:
            _schema(data)
        except vol.MultipleInvalid as err:
            schema_errors = err
        try:
            validate_version(data)
        except vol.Invalid as err:
            if schema_errors:
                schema_errors.add(err)
            else:
                raise
        if schema_errors:
            raise schema_errors
        return data

    return validate_repo_data


def validate_version(data: Any) -> Any:
    """Ensure at least one of last_commit or last_version is present."""
    if "last_commit" not in data and "last_version" not in data:
        raise vol.Invalid("Expected at least one of [`last_commit`, `last_version`], got none")
    return data


V2_COMMON_DATA_JSON_SCHEMA = {
    vol.Required("description"): vol.Any(str, None),
    vol.Optional("downloads"): int,
    vol.Optional("etag_releases"): str,
    vol.Required("etag_repository"): str,
    vol.Required("full_name"): str,
    vol.Optional("last_commit"): str,
    vol.Required("last_fetched"): vol.Any(int, float),
    vol.Required("last_updated"): str,
    vol.Optional("last_version"): str,
    vol.Optional("prerelease"): str,
    vol.Required("manifest"): {
        vol.Optional("country"): vol.Any([str], False),
        vol.Optional("name"): str,
    },
    vol.Optional("open_issues"): int,
    vol.Optional("stargazers_count"): int,
    vol.Optional("topics"): [str],
}

V2_INTEGRATION_DATA_JSON_SCHEMA = {
    **V2_COMMON_DATA_JSON_SCHEMA,
    vol.Required("domain"): str,
    vol.Required("manifest_name"): str,
}

_V2_REPO_SCHEMAS = {
    "appdaemon": V2_COMMON_DATA_JSON_SCHEMA,
    "integration": V2_INTEGRATION_DATA_JSON_SCHEMA,
    "plugin": V2_COMMON_DATA_JSON_SCHEMA,
    "python_script": V2_COMMON_DATA_JSON_SCHEMA,
    "template": V2_COMMON_DATA_JSON_SCHEMA,
    "theme": V2_COMMON_DATA_JSON_SCHEMA,
}

# Used when validating repos in the hacs integration, discards extra keys
VALIDATE_FETCHED_V2_REPO_DATA = {
    category: validate_repo_data(schema, vol.REMOVE_EXTRA)
    for category, schema in _V2_REPO_SCHEMAS.items()
}

# Used when validating repos when generating data, fails on extra keys
VALIDATE_GENERATED_V2_REPO_DATA = {
    category: vol.Schema({str: validate_repo_data(schema, vol.PREVENT_EXTRA)})
    for category, schema in _V2_REPO_SCHEMAS.items()
}

V2_CRITICAL_REPO_DATA_SCHEMA = {
    vol.Required("link"): str,
    vol.Required("reason"): str,
    vol.Required("repository"): str,
}

# Used when validating critical repos in the hacs integration, discards extra keys
VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA = vol.Schema(
    V2_CRITICAL_REPO_DATA_SCHEMA,
    extra=vol.REMOVE_EXTRA,
)

# Used when validating critical repos when generating data, fails on extra keys
VALIDATE_GENERATED_V2_CRITICAL_REPO_SCHEMA = vol.Schema(
    [
        vol.Schema(
            V2_CRITICAL_REPO_DATA_SCHEMA,
            extra=vol.PREVENT_EXTRA,
        )
    ]
)

V2_REMOVED_REPO_DATA_SCHEMA = {
    vol.Optional("link"): str,
    vol.Optional("reason"): str,
    vol.Required("removal_type"): vol.In(
        [
            "Integration is missing a version, and is abandoned.",
            "Remove",
            "archived",
            "blacklist",
            "critical",
            "deprecated",
            "removal",
            "remove",
            "removed",
            "replaced",
            "repository",
        ]
    ),
    vol.Required("repository"): str,
}

# Used when validating removed repos in the hacs integration, discards extra keys
VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA = vol.Schema(
    V2_REMOVED_REPO_DATA_SCHEMA,
    extra=vol.REMOVE_EXTRA,
)

# Used when validating removed repos when generating data, fails on extra keys
VALIDATE_GENERATED_V2_REMOVED_REPO_SCHEMA = vol.Schema(
    [
        vol.Schema(
            V2_REMOVED_REPO_DATA_SCHEMA,
            extra=vol.PREVENT_EXTRA,
        )
    ]
)
