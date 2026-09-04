"""Unit tests for TrueNASEntityDescription validation."""

from __future__ import annotations

import logging

import pytest

from homeassistant.components.truenas_ce.entity import (
    TrueNASEntityDescription,
    _composite_references,
    format_unique_id,
)

_LOGGER = logging.getLogger(__name__)


def test_valid_static_description() -> None:
    """A static description with a data_reference is accepted as-is."""
    desc = TrueNASEntityDescription(
        key="test",
        name="Test",
        data_path="app",
        data_reference="app_name",
    )
    assert desc.key == "test"


def test_valid_dynamic_description_with_reference() -> None:
    """A dynamic-keys description with a data_reference is accepted as-is."""
    desc = TrueNASEntityDescription(
        key="test_dynamic",
        name="Test Dynamic",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_reference="app_name",
    )
    assert desc.key == "test_dynamic"


def test_valid_dynamic_description_with_composite() -> None:
    """A dynamic-keys description with composite references is accepted as-is."""
    desc = TrueNASEntityDescription(
        key="test_net",
        name="Test Net",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_composite_references=("networks", "interface_name"),
    )
    assert desc.key == "test_net"


def test_composite_references_require_dynamic_keys(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Composite references without data_dynamic_keys=True log a single warning."""
    with caplog.at_level(logging.WARNING, logger=_LOGGER.name):
        TrueNASEntityDescription(
            key="test_bad",
            name="Test Bad",
            data_path="app_stats",
            data_composite_references=("networks", "interface_name"),
        )
    assert len(caplog.records) == 1
    assert "data_composite_references requires data_dynamic_keys=True" in caplog.text


def test_composite_references_too_few_segments(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A composite reference with only one segment logs a single warning."""
    with caplog.at_level(logging.WARNING, logger=_LOGGER.name):
        TrueNASEntityDescription(
            key="test_bad",
            name="Test Bad",
            data_path="app_stats",
            data_dynamic_keys=True,
            data_composite_references=("only_one",),
        )
    assert len(caplog.records) == 1
    assert "exactly two segments" in caplog.text


def test_composite_references_too_many_segments(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A composite reference with more than two segments logs a single warning."""
    with caplog.at_level(logging.WARNING, logger=_LOGGER.name):
        TrueNASEntityDescription(
            key="test_bad",
            name="Test Bad",
            data_path="app_stats",
            data_dynamic_keys=True,
            data_composite_references=("a", "b", "c"),
        )
    assert len(caplog.records) == 1
    assert "exactly two segments" in caplog.text


def test_dynamic_keys_without_reference_or_composite(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dynamic keys without a reference or composite references log a warning."""
    with caplog.at_level(logging.WARNING, logger=_LOGGER.name):
        TrueNASEntityDescription(
            key="test_bad",
            name="Test Bad",
            data_path="app_stats",
            data_dynamic_keys=True,
        )
    assert len(caplog.records) == 1
    assert (
        "data_dynamic_keys=True requires either data_reference or"
        " data_composite_references"
    ) in caplog.text


def test_composite_references_returns_unique_ids() -> None:
    """Composite references produce one unique id per leaf value across entries."""
    description = TrueNASEntityDescription(
        key="test_net",
        name="Test Net",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_composite_references=("networks", "interface_name"),
    )
    data = {
        "app1": {
            "networks": [
                {"interface_name": "eth0", "rx_bytes": 100},
                {"interface_name": "eth1", "rx_bytes": 200},
            ]
        },
        "app2": {
            "networks": [
                {"interface_name": "eth0", "rx_bytes": 300},
            ]
        },
        "app3": {
            "other": "not-a-list",
        },
    }
    result = _composite_references("inst", description, data)
    assert result == {
        format_unique_id("inst", "test_net", "app1::eth0"),
        format_unique_id("inst", "test_net", "app1::eth1"),
        format_unique_id("inst", "test_net", "app2::eth0"),
    }


def test_composite_references_ignores_non_list_container() -> None:
    """A non-list container value at the segment path yields no unique ids."""
    description = TrueNASEntityDescription(
        key="test_net",
        name="Test Net",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_composite_references=("networks", "interface_name"),
    )
    data = {
        "app1": {
            "networks": "not-a-list",
        }
    }
    result = _composite_references("inst", description, data)
    assert result == set()


def test_composite_references_invalid_length_returns_empty_set() -> None:
    """A malformed (non-2-segment) composite reference yields no unique ids.

    __post_init__ only logs a warning for this (frozen dataclasses can't
    reject construction), so callers must not assume the tuple is unpackable.
    """
    description = TrueNASEntityDescription(
        key="test_net",
        name="Test Net",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_composite_references=("only_one",),
    )
    data = {"app1": {"networks": [{"interface_name": "eth0"}]}}
    result = _composite_references("inst", description, data)
    assert result == set()


def test_composite_references_empty_data() -> None:
    """Empty source data yields no unique ids."""
    description = TrueNASEntityDescription(
        key="test_net",
        name="Test Net",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_composite_references=("networks", "interface_name"),
    )
    result = _composite_references("inst", description, {})
    assert result == set()


def test_composite_references_ignores_missing_or_null_leaf_key() -> None:
    """Entries with a missing or null leaf key are skipped, others still produce ids."""
    description = TrueNASEntityDescription(
        key="test_net",
        name="Test Net",
        data_path="app_stats",
        data_dynamic_keys=True,
        data_composite_references=("networks", "interface_name"),
    )
    data = {
        "app1": {
            "networks": [
                {"interface_name": "eth0"},
                {"interface_name": None},
                {},
                {"interface_name": "eth1"},
            ],
        },
        "app2": {
            "networks": [
                {"interface_name": None},
                {},
            ],
        },
    }

    result = _composite_references("inst", description, data)

    assert result == {
        format_unique_id("inst", "test_net", "app1::eth0"),
        format_unique_id("inst", "test_net", "app1::eth1"),
    }
