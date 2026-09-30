"""Tests for the Marketplace data schemas."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from typing import Any

from probatio.error import Invalid, MultipleInvalid
import pytest

from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.components.marketplace.utils.validate import (
    VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA,
    VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA,
    VALIDATE_FETCHED_V2_REPO_DATA,
)

from tests.common import load_json_array_fixture, load_json_object_fixture

CATEGORIES = (
    "integration",
    "plugin",
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
    "full_name": "owner/blah",
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
            GOOD_COMMON_DATA | {"manifest": {"country": "NO"}},
            does_not_raise(),
            id="country",
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
            GOOD_COMMON_DATA | {"last_version": "release/1.0.0-beta.1"},
            does_not_raise(),
            id="last-version-with-slash",
        ),
        *(
            pytest.param(
                GOOD_COMMON_DATA | {key: version},
                pytest.raises(Invalid),
                id=f"{key}-{name}",
            )
            for key in ("last_commit", "last_version", "prerelease")
            for name, version in (
                ("parent", "../../other/repository/archive/refs/tags/1.0"),
                ("encoded-parent", "%2e%2e/%2e%2e/other"),
                ("hidden", ".hidden"),
                ("query", "1.0?raw=true"),
                ("fragment", "1.0#readme"),
                ("empty", ""),
            )
        ),
        *(
            pytest.param(
                GOOD_COMMON_DATA | {"full_name": full_name},
                pytest.raises(Invalid),
                id=f"full-name-{name}",
            )
            for name, full_name in (
                ("parent", "owner/.."),
                ("current", "owner/."),
                ("parent-owner", "../repository"),
                ("nested", "owner/repository/extra"),
                ("no-owner", "repository"),
            )
        ),
        pytest.param(
            GOOD_COMMON_DATA | {"extra": "key"},
            does_not_raise(),
            id="extra-key-is-discarded",
        ),
        *(
            pytest.param(
                GOOD_COMMON_DATA | {"last_fetched": last_fetched},
                pytest.raises(Invalid),
                id=f"last-fetched-{name}",
            )
            for name, last_fetched in (
                ("milliseconds", 1_700_000_000_000),
                ("negative", -1),
                ("far-future", 1e20),
            )
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
        *(
            pytest.param(
                GOOD_INTEGRATION_DATA | {"domain": domain},
                pytest.raises(Invalid),
                id=f"domain-{name}",
            )
            for name, domain in (
                ("parent", "../.."),
                ("path", "custom/light"),
                ("uppercase", "Light"),
                ("empty", ""),
            )
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
        *(
            pytest.param(category, GOOD_COMMON_DATA, id=category)
            for category in COMMON_CATEGORIES
        ),
        pytest.param("integration", GOOD_INTEGRATION_DATA, id="integration"),
    ],
)
def test_repo_data_keeps_only_catalog_keys(category: str, data: dict[str, Any]) -> None:
    """Test the catalog cannot set what only the Marketplace knows."""
    validated = VALIDATE_FETCHED_V2_REPO_DATA[category](
        data
        | {
            "category": "theme",
            "id": "1",
            "installed": True,
            "installed_version": "9.9",
        }
    )

    assert validated == data


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
