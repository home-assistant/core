"""Tests for the Bosch Smart Home Camera config/options flow helpers."""

import base64
import json

import pytest

from homeassistant.components.bosch_shc_camera.config_flow import (
    _detect_token_client_id,
    _flatten_sections,
)


def test_flatten_sections_empty() -> None:
    """An empty submit dict flattens to an empty dict."""
    assert _flatten_sections({}) == {}


def test_flatten_sections_single_section() -> None:
    """Fields nested under one section key are lifted to the top level."""
    user_input = {"features": {"enable_snapshots": False}}
    assert _flatten_sections(user_input) == {"enable_snapshots": False}


def test_flatten_sections_multiple_sections() -> None:
    """Fields from multiple sections are merged into one flat dict."""
    user_input = {
        "features": {"enable_snapshots": False},
        "auth": {"migrate_to_oss_client": True},
    }
    assert _flatten_sections(user_input) == {
        "enable_snapshots": False,
        "migrate_to_oss_client": True,
    }


def test_flatten_sections_missing_section_is_treated_as_empty() -> None:
    """A section key HA omitted (empty section) does not raise."""
    user_input = {"features": {"enable_snapshots": False}}
    # "events_storage"/"auth" section keys are absent entirely — must not raise.
    assert _flatten_sections(user_input) == {"enable_snapshots": False}


def test_flatten_sections_passes_through_non_section_keys() -> None:
    """Top-level keys that aren't section keys pass through unchanged."""
    user_input = {
        "features": {"enable_snapshots": False},
        "some_legacy_flat_key": "value",
    }
    assert _flatten_sections(user_input) == {
        "enable_snapshots": False,
        "some_legacy_flat_key": "value",
    }


def test_flatten_sections_duplicate_key_across_sections_raises() -> None:
    """Two sections both defining the same field name raises ValueError."""
    user_input = {
        "features": {"enable_snapshots": False},
        "auth": {"enable_snapshots": True},
    }
    with pytest.raises(ValueError, match="duplicate key"):
        _flatten_sections(user_input)


def test_flatten_sections_duplicate_top_level_and_section_raises() -> None:
    """A top-level key colliding with a section-provided field raises ValueError."""
    user_input = {
        "features": {"enable_snapshots": False},
        "enable_snapshots": True,
    }
    with pytest.raises(ValueError, match="duplicate key"):
        _flatten_sections(user_input)


def test_flatten_sections_does_not_mutate_input() -> None:
    """The input dict is never mutated."""
    user_input = {"features": {"enable_snapshots": False}}
    original = {"features": {"enable_snapshots": False}}
    _flatten_sections(user_input)
    assert user_input == original


@pytest.mark.parametrize(
    ("bearer_token", "expected"),
    [
        pytest.param("", None, id="empty-token"),
        pytest.param("not-a-jwt", None, id="not-enough-parts"),
        pytest.param(
            "only.onepart", None, id="two-parts-no-padding-issue-but-bad-json"
        ),
    ],
)
def test_detect_token_client_id_invalid_tokens(
    bearer_token: str, expected: str | None
) -> None:
    """Malformed tokens return None instead of raising."""
    assert _detect_token_client_id(bearer_token) == expected


def test_detect_token_client_id_valid_jwt() -> None:
    """A well-formed JWT's `azp` claim is extracted."""
    payload = base64.urlsafe_b64encode(
        json.dumps({"azp": "oss_residential_app"}).encode()
    ).rstrip(b"=")
    token = f"header.{payload.decode()}.signature"
    assert _detect_token_client_id(token) == "oss_residential_app"


def test_detect_token_client_id_missing_azp_claim() -> None:
    """A valid JWT without an `azp` claim returns None."""
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "x"}).encode()).rstrip(b"=")
    token = f"header.{payload.decode()}.signature"
    assert _detect_token_client_id(token) is None
