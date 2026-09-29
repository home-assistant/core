"""Validation utilities."""

from collections.abc import Callable
from dataclasses import dataclass, field
import re
from typing import Any

from awesomeversion import AwesomeVersion
import probatio

from homeassistant.helpers.config_validation import url as url_validator


@dataclass
class Validate:
    """Validate."""

    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return bool if the validation was a success."""
        return len(self.errors) == 0


# The catalog is remote input: these end up in URLs and in paths on disk
VALID_FULL_NAME = re.compile(r"^[A-Za-z0-9-]+/(?!\.\.?$)[A-Za-z0-9_.-]+$")
# Not the stricter domain of Core, the catalog has integrations with a hyphen
VALID_DOMAIN = re.compile(r"^[a-z0-9_-]+$")
# URLs collapse dot segments, even encoded ones, and cut at a query or fragment
INVALID_REF = re.compile(r"(^|/)\.|[?#%\\\s]")
# The last second a datetime can hold, a timestamp in milliseconds is far past it
MAX_TIMESTAMP = 253402300799


def valid_ref(value: Any) -> str:
    """Validate a tag, branch or commit the catalog wants installed."""
    if not isinstance(value, str) or not value or INVALID_REF.search(value):
        raise probatio.Invalid(f"'{value}' is not a usable version")
    return value


def is_valid_ref(value: Any) -> bool:
    """Return if a tag, branch or commit can be installed."""
    try:
        valid_ref(value)
    except probatio.Invalid:
        return False
    return True


def valid_version(value: Any) -> str:
    """Validate a Home Assistant version a repository needs."""
    if not isinstance(value, str) or not AwesomeVersion(value).valid:
        raise probatio.Invalid(f"'{value}' is not a version")
    return value


# What the Marketplace reads from hacs.json, a value of another type is left out
REPOSITORY_MANIFEST_VALUES = {
    "content_in_root": probatio.Schema(bool),
    "filename": probatio.Schema(str),
    "hacs": probatio.Schema(str),
    "hide_default_branch": probatio.Schema(bool),
    "homeassistant": probatio.Schema(valid_version),
    "name": probatio.Schema(str),
    "persistent_directory": probatio.Schema(str),
    "zip_release": probatio.Schema(bool),
}


REPOSITORY_MANIFEST_JSON_SCHEMA = probatio.Schema(
    {
        probatio.Optional("content_in_root"): bool,
        # Accepted for existing repositories, the Marketplace ignores it
        probatio.Optional("country"): object,
        probatio.Optional("filename"): str,
        probatio.Optional("hacs"): str,
        probatio.Optional("hide_default_branch"): bool,
        probatio.Optional("homeassistant"): str,
        probatio.Optional("persistent_directory"): str,
        # Accepted for existing repositories, the README is always shown
        probatio.Optional("render_readme"): bool,
        probatio.Optional("zip_release"): bool,
        probatio.Required("name"): str,
    },
    extra=probatio.PREVENT_EXTRA,
)

INTEGRATION_MANIFEST_JSON_SCHEMA = probatio.Schema(
    {
        probatio.Required("codeowners"): list,
        probatio.Required("documentation"): url_validator,
        probatio.Required("domain"): str,
        probatio.Required("issue_tracker"): url_validator,
        probatio.Required("name"): str,
        probatio.Required("version"): probatio.Coerce(AwesomeVersion),
    },
    extra=probatio.ALLOW_EXTRA,
)


def validate_repo_data(schema: dict[Any, Any], extra: int) -> Callable[[Any], Any]:
    """Return a validator for repo data.

    This is used instead of probatio.All to always try both the repo schema and
    and the validate_version validator.
    """
    _schema = probatio.Schema(schema, extra=extra)

    def _validate(data: Any) -> Any:
        """Validate integration repo data."""
        schema_errors: probatio.MultipleInvalid | None = None
        try:
            data = _schema(data)
        except probatio.MultipleInvalid as err:
            schema_errors = err
        try:
            validate_version(data)
        except probatio.Invalid as err:
            if schema_errors:
                schema_errors.add(err)
            else:
                raise
        if schema_errors:
            raise schema_errors
        return data

    return _validate


def validate_version(data: Any) -> Any:
    """Ensure at least one of last_commit or last_version is present."""
    if "last_commit" not in data and "last_version" not in data:
        raise probatio.Invalid(
            "Expected at least one of [`last_commit`, `last_version`], got none"
        )
    return data


V2_COMMON_DATA_JSON_SCHEMA = {
    probatio.Required("description"): probatio.Any(str, None),
    probatio.Optional("downloads"): int,
    probatio.Optional("etag_releases"): str,
    probatio.Required("etag_repository"): str,
    probatio.Required("full_name"): probatio.All(str, probatio.Match(VALID_FULL_NAME)),
    probatio.Optional("last_commit"): valid_ref,
    probatio.Required("last_fetched"): probatio.All(
        probatio.Any(int, float), probatio.Range(min=0, max=MAX_TIMESTAMP)
    ),
    probatio.Required("last_updated"): str,
    probatio.Optional("last_version"): valid_ref,
    probatio.Optional("prerelease"): valid_ref,
    probatio.Required("manifest"): {
        # Accepted for existing repositories, the Marketplace ignores it
        probatio.Optional("country"): object,
        probatio.Optional("name"): str,
    },
    probatio.Optional("open_issues"): int,
    probatio.Optional("stargazers_count"): int,
    probatio.Optional("topics"): [str],
}

V2_INTEGRATION_DATA_JSON_SCHEMA = {
    **V2_COMMON_DATA_JSON_SCHEMA,
    probatio.Required("domain"): probatio.All(str, probatio.Match(VALID_DOMAIN)),
    probatio.Required("manifest_name"): str,
}

_V2_REPO_SCHEMAS = {
    "integration": V2_INTEGRATION_DATA_JSON_SCHEMA,
    "plugin": V2_COMMON_DATA_JSON_SCHEMA,
    "template": V2_COMMON_DATA_JSON_SCHEMA,
    "theme": V2_COMMON_DATA_JSON_SCHEMA,
}

# Used when validating repos in the Marketplace, discards extra keys
VALIDATE_FETCHED_V2_REPO_DATA = {
    category: validate_repo_data(schema, probatio.REMOVE_EXTRA)
    for category, schema in _V2_REPO_SCHEMAS.items()
}

V2_CRITICAL_REPO_DATA_SCHEMA = {
    probatio.Required("link"): str,
    probatio.Required("reason"): str,
    probatio.Required("repository"): str,
}

# Used when validating critical repos in the Marketplace, discards extra keys
VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA = probatio.Schema(
    V2_CRITICAL_REPO_DATA_SCHEMA,
    extra=probatio.REMOVE_EXTRA,
)

V2_REMOVED_REPO_DATA_SCHEMA = {
    probatio.Optional("link"): str,
    probatio.Optional("reason"): str,
    probatio.Required("removal_type"): probatio.In(
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
    probatio.Required("repository"): str,
}

# Used when validating removed repos in the Marketplace, discards extra keys
VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA = probatio.Schema(
    V2_REMOVED_REPO_DATA_SCHEMA,
    extra=probatio.REMOVE_EXTRA,
)
