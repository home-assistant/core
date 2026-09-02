"""Tests for the Community store data schemas."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
import re
from typing import Any

from awesomeversion import AwesomeVersion
import pytest
from voluptuous.error import Invalid, MultipleInvalid

from homeassistant.components.store.const import DOMAIN
from homeassistant.components.store.utils.validate import (
    HACS_MANIFEST_JSON_SCHEMA,
    INTEGRATION_MANIFEST_JSON_SCHEMA,
    VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA,
    VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA,
    VALIDATE_FETCHED_V2_REPO_DATA,
)

from tests.common import load_json_array_fixture, load_json_object_fixture

CATEGORIES = (
    "appdaemon",
    "integration",
    "plugin",
    "python_script",
    "template",
    "theme",
)

# Every category but integration shares the same shape.
COMMON_CATEGORIES = tuple(
    category for category in CATEGORIES if category != "integration"
)

GOOD_COMMON_DATA = {
    "description": "abc",
    "etag_repository": "blah",
    "full_name": "blah",
    "last_commit": "abc",
    "last_fetched": 0,
    "last_updated": "blah",
    "manifest": {},
}

GOOD_INTEGRATION_DATA = GOOD_COMMON_DATA | {
    "domain": "abc",
    "manifest_name": "abc",
}


def without(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a copy of the data without the given key."""
    return {name: value for name, value in data.items() if name != key}


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(
            {"name": "My awesome thing", "homeassistant": "1.2"},
            {"name": "My awesome thing", "homeassistant": AwesomeVersion("1.2")},
            id="homeassistant",
        ),
        pytest.param(
            {"name": "My awesome thing", "hacs": "1.2"},
            {"name": "My awesome thing", "hacs": AwesomeVersion("1.2")},
            id="hacs",
        ),
        pytest.param(
            {"name": "My awesome thing", "country": ["NO"]},
            {"name": "My awesome thing", "country": ["NO"]},
            id="country-list",
        ),
        pytest.param(
            {"name": "My awesome thing", "country": "NO"},
            {"name": "My awesome thing", "country": ["NO"]},
            id="country-string",
        ),
        pytest.param(
            {"name": "My awesome thing", "country": "no"},
            {"name": "My awesome thing", "country": ["NO"]},
            id="country-lowercase",
        ),
        pytest.param(
            {"name": "My awesome thing"},
            {"name": "My awesome thing"},
            id="name-only",
        ),
        pytest.param(
            {
                "name": "My awesome thing",
                "content_in_root": True,
                "zip_release": True,
                "filename": "my_super_awesome_thing.js",
                "render_readme": True,
                "hide_default_branch": True,
                "country": ["NO", "SE", "DK"],
                "persistent_directory": "userfiles",
            },
            {
                "name": "My awesome thing",
                "content_in_root": True,
                "zip_release": True,
                "filename": "my_super_awesome_thing.js",
                "render_readme": True,
                "hide_default_branch": True,
                "country": ["NO", "SE", "DK"],
                "persistent_directory": "userfiles",
            },
            id="everything",
        ),
    ],
)
def test_hacs_manifest_json_schema(
    data: dict[str, Any], expected: dict[str, Any]
) -> None:
    """Test validating the hacs.json of a repository."""
    assert HACS_MANIFEST_JSON_SCHEMA(data) == expected


@pytest.mark.parametrize(
    ("data", "match"),
    [
        pytest.param(
            {"name": "My awesome thing", "not": "valid"},
            r"extra keys not allowed|not a valid option",
            id="extra-key",
        ),
        pytest.param(
            {"name": "My awesome thing", "country": "not_valid"},
            "Value 'NOT_VALID' is not in",
            id="unknown-country",
        ),
        pytest.param(
            {"name": "My awesome thing", "country": False},
            re.escape("Value 'False' is not a string or list."),
            id="country-wrong-type",
        ),
        pytest.param({}, "required key not provided", id="missing-name"),
    ],
)
def test_hacs_manifest_json_schema_bad_data(data: dict[str, Any], match: str) -> None:
    """Test rejecting an invalid hacs.json."""
    with pytest.raises(Invalid, match=match):
        HACS_MANIFEST_JSON_SCHEMA(data)


def test_integration_manifest_json_schema() -> None:
    """Test validating the manifest.json of an integration repository."""
    data = {
        "issue_tracker": "https://hacs.xyz/",
        "name": "My awesome thing",
        "version": "1.2",
        "domain": "myawesomething",
        "codeowners": ["test"],
        "documentation": "https://hacs.xyz/",
    }

    validated = INTEGRATION_MANIFEST_JSON_SCHEMA(data)

    assert validated["version"] == AwesomeVersion("1.2")
    assert validated == data


def test_integration_manifest_json_schema_bad_data() -> None:
    """Test rejecting an invalid integration manifest.json."""
    with pytest.raises(Invalid, match="expected str"):
        INTEGRATION_MANIFEST_JSON_SCHEMA(
            {
                "issue_tracker": "https://hacs.xyz/",
                "name": "My awesome thing",
                "version": "1.2",
                "domain": None,
                "codeowners": ["test"],
                "documentation": "https://hacs.xyz/",
            }
        )


def test_critical_repo_data_json_schema() -> None:
    """Test validating the recorded critical repository data."""
    for repository in load_json_array_fixture("v2-critical-data.json", DOMAIN):
        VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA(repository)


@pytest.mark.parametrize(
    ("data", "expectation"),
    [
        pytest.param(
            {"repository": "test", "reason": "blah", "link": "https://blah"},
            does_not_raise(),
            id="good",
        ),
        pytest.param({}, pytest.raises(Invalid), id="empty"),
        pytest.param(
            {"repository": "test", "reason": "blah"},
            pytest.raises(Invalid),
            id="missing-link",
        ),
        pytest.param(
            {"repository": "test", "link": "https://blah"},
            pytest.raises(Invalid),
            id="missing-reason",
        ),
        pytest.param(
            {"reason": "blah", "link": "https://blah"},
            pytest.raises(Invalid),
            id="missing-repository",
        ),
        pytest.param(
            {"repository": 123, "reason": "blah", "link": "https://blah"},
            pytest.raises(Invalid),
            id="repository-wrong-type",
        ),
        pytest.param(
            {"repository": "test", "reason": 123, "link": "https://blah"},
            pytest.raises(Invalid),
            id="reason-wrong-type",
        ),
        pytest.param(
            {"repository": "test", "reason": "blah", "link": 123},
            pytest.raises(Invalid),
            id="link-wrong-type",
        ),
        pytest.param(
            {
                "repository": "test",
                "reason": "blah",
                "link": "https://blah",
                "extra": "key",
            },
            does_not_raise(),
            id="extra-key-is-discarded",
        ),
    ],
)
def test_critical_repo_data_json_schema_bad_data(
    data: dict[str, Any], expectation: AbstractContextManager[Any]
) -> None:
    """Test validating a single critical repository entry."""
    with expectation:
        VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA(data)


@pytest.mark.parametrize("category", CATEGORIES)
def test_repo_data_json_schema(category: str) -> None:
    """Test validating the recorded repository data of every category."""
    data = load_json_object_fixture(f"v2-{category}-data.json", DOMAIN)
    for repository in data.values():
        VALIDATE_FETCHED_V2_REPO_DATA[category](repository)


@pytest.mark.parametrize("category", COMMON_CATEGORIES)
@pytest.mark.parametrize(
    ("data", "expectation"),
    [
        pytest.param(GOOD_COMMON_DATA, does_not_raise(), id="good"),
        pytest.param(
            without(GOOD_COMMON_DATA, "last_commit") | {"last_version": "123"},
            does_not_raise(),
            id="last-version-instead-of-last-commit",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"last_version": "123"},
            does_not_raise(),
            id="both-versions",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"last_version": "123", "prerelease": "1.2.3"},
            does_not_raise(),
            id="prerelease",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"last_version": "123", "prerelease": None},
            pytest.raises(Invalid),
            id="prerelease-none",
        ),
        pytest.param(
            without(GOOD_COMMON_DATA, "description"),
            pytest.raises(Invalid),
            id="missing-description",
        ),
        pytest.param(
            without(GOOD_COMMON_DATA, "etag_repository"),
            pytest.raises(Invalid),
            id="missing-etag-repository",
        ),
        pytest.param(
            without(GOOD_COMMON_DATA, "full_name"),
            pytest.raises(Invalid),
            id="missing-full-name",
        ),
        pytest.param(
            without(GOOD_COMMON_DATA, "last_commit"),
            pytest.raises(Invalid),
            id="missing-both-versions",
        ),
        pytest.param(
            without(GOOD_COMMON_DATA, "last_fetched"),
            pytest.raises(Invalid),
            id="missing-last-fetched",
        ),
        pytest.param(
            without(GOOD_COMMON_DATA, "last_updated"),
            pytest.raises(Invalid),
            id="missing-last-updated",
        ),
        pytest.param(
            without(GOOD_COMMON_DATA, "manifest"),
            pytest.raises(Invalid),
            id="missing-manifest",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"description": 123},
            pytest.raises(Invalid),
            id="description-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"etag_repository": 123},
            pytest.raises(Invalid),
            id="etag-repository-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"full_name": 123},
            pytest.raises(Invalid),
            id="full-name-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"last_commit": 123},
            pytest.raises(Invalid),
            id="last-commit-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"last_fetched": "blah"},
            pytest.raises(Invalid),
            id="last-fetched-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"last_updated": 123},
            pytest.raises(Invalid),
            id="last-updated-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"manifest": 123},
            pytest.raises(Invalid),
            id="manifest-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"downloads": "many"},
            pytest.raises(Invalid),
            id="downloads-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"etag_releases": 123},
            pytest.raises(Invalid),
            id="etag-releases-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"last_version": 123},
            pytest.raises(Invalid),
            id="last-version-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"open_issues": "many"},
            pytest.raises(Invalid),
            id="open-issues-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"stargazers_count": "many"},
            pytest.raises(Invalid),
            id="stargazers-count-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"topics": 123},
            pytest.raises(Invalid),
            id="topics-wrong-type",
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"extra": "key"},
            does_not_raise(),
            id="extra-key-is-discarded",
        ),
    ],
)
def test_common_repo_data_json_schema_bad_data(
    category: str, data: dict[str, Any], expectation: AbstractContextManager[Any]
) -> None:
    """Test validating a single repository entry of a non integration category."""
    with expectation:
        VALIDATE_FETCHED_V2_REPO_DATA[category](data)


@pytest.mark.parametrize(
    ("data", "expectation"),
    [
        pytest.param(GOOD_INTEGRATION_DATA, does_not_raise(), id="good"),
        pytest.param(
            without(GOOD_INTEGRATION_DATA, "last_commit") | {"last_version": "123"},
            does_not_raise(),
            id="last-version-instead-of-last-commit",
        ),
        pytest.param(
            GOOD_INTEGRATION_DATA | {"last_version": "123", "prerelease": "1.2.3"},
            does_not_raise(),
            id="prerelease",
        ),
        pytest.param(
            without(GOOD_INTEGRATION_DATA, "domain"),
            pytest.raises(Invalid),
            id="missing-domain",
        ),
        pytest.param(
            without(GOOD_INTEGRATION_DATA, "manifest_name"),
            pytest.raises(Invalid),
            id="missing-manifest-name",
        ),
        pytest.param(
            GOOD_INTEGRATION_DATA | {"domain": 123},
            pytest.raises(Invalid),
            id="domain-wrong-type",
        ),
        pytest.param(
            GOOD_INTEGRATION_DATA | {"manifest_name": 123},
            pytest.raises(Invalid),
            id="manifest-name-wrong-type",
        ),
        pytest.param(
            GOOD_INTEGRATION_DATA | {"extra": "key"},
            does_not_raise(),
            id="extra-key-is-discarded",
        ),
    ],
)
def test_integration_repo_data_json_schema_bad_data(
    data: dict[str, Any], expectation: AbstractContextManager[Any]
) -> None:
    """Test validating a single integration repository entry."""
    with expectation:
        VALIDATE_FETCHED_V2_REPO_DATA["integration"](data)


@pytest.mark.parametrize(
    ("category", "data"),
    [
        pytest.param(
            category,
            {
                "etag_repository": "blah",
                "full_name": 123,
                "last_fetched": 0,
                "last_updated": "blah",
                "manifest": {},
            },
            id=category,
        )
        for category in COMMON_CATEGORIES
    ]
    + [
        pytest.param(
            "integration",
            {
                "domain": "abc",
                "etag_repository": "blah",
                "full_name": 123,
                "last_fetched": 0,
                "last_updated": "blah",
                "manifest": {},
                "manifest_name": "abc",
            },
            id="integration",
        )
    ],
)
def test_repo_data_json_schema_multiple_bad_data(
    category: str, data: dict[str, Any]
) -> None:
    """Test that schema errors and the custom version check are reported together."""
    with pytest.raises(MultipleInvalid) as exc_info:
        VALIDATE_FETCHED_V2_REPO_DATA[category](data)

    assert {(error.msg, tuple(error.path)) for error in exc_info.value.errors} == {
        ("expected str", ("full_name",)),
        ("required key not provided", ("description",)),
        ("Expected at least one of [`last_commit`, `last_version`], got none", ()),
    }


def test_removed_repo_data_json_schema() -> None:
    """Test validating the recorded removed repository data."""
    for repository in load_json_array_fixture("v2-removed-data.json", DOMAIN):
        VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA(repository)


@pytest.mark.parametrize(
    ("data", "expectation"),
    [
        pytest.param(
            {"removal_type": "critical", "repository": "test"},
            does_not_raise(),
            id="good",
        ),
        pytest.param({}, pytest.raises(Invalid), id="empty"),
        pytest.param(
            {"repository": "test"},
            pytest.raises(Invalid),
            id="missing-removal-type",
        ),
        pytest.param(
            {"removal_type": "critical"},
            pytest.raises(Invalid),
            id="missing-repository",
        ),
        pytest.param(
            {
                "link": 123,
                "reason": "blah",
                "removal_type": "critical",
                "repository": "test",
            },
            pytest.raises(Invalid),
            id="link-wrong-type",
        ),
        pytest.param(
            {
                "link": "https://blah",
                "reason": 123,
                "removal_type": "critical",
                "repository": "test",
            },
            pytest.raises(Invalid),
            id="reason-wrong-type",
        ),
        pytest.param(
            {
                "link": "https://blah",
                "reason": "blah",
                "removal_type": 123,
                "repository": "test",
            },
            pytest.raises(Invalid),
            id="removal-type-wrong-type",
        ),
        pytest.param(
            {
                "link": "https://blah",
                "reason": "blah",
                "removal_type": "bad",
                "repository": "test",
            },
            pytest.raises(Invalid),
            id="unknown-removal-type",
        ),
        pytest.param(
            {
                "link": "https://blah",
                "reason": "blah",
                "removal_type": "critical",
                "repository": 123,
            },
            pytest.raises(Invalid),
            id="repository-wrong-type",
        ),
        pytest.param(
            {
                "link": "https://blah",
                "reason": "blah",
                "removal_type": "critical",
                "repository": "test",
                "extra": "key",
            },
            does_not_raise(),
            id="extra-key-is-discarded",
        ),
    ],
)
def test_removed_repo_data_json_schema_bad_data(
    data: dict[str, Any], expectation: AbstractContextManager[Any]
) -> None:
    """Test validating a single removed repository entry."""
    with expectation:
        VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA(data)
