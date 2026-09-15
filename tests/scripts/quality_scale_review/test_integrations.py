"""Tests for script.quality_scale_review.integrations."""

from pathlib import Path

import pytest

from script.quality_scale_review import integrations


@pytest.mark.parametrize(
    ("filenames", "expected"),
    [
        pytest.param(
            ["homeassistant/components/peblar/sensor.py"], ["peblar"], id="component"
        ),
        pytest.param(["tests/components/peblar/test_sensor.py"], ["peblar"], id="test"),
        pytest.param(
            [
                "tests/components/peblar/test_sensor.py",
                "homeassistant/components/peblar/sensor.py",
                "homeassistant/components/adax/climate.py",
            ],
            ["adax", "peblar"],
            id="deduplicated-and-sorted",
        ),
        pytest.param(
            ["homeassistant/helpers/entity.py", "script/hassfest/__main__.py"],
            [],
            id="outside-components",
        ),
        pytest.param(
            ["homeassistant/components/peblar"], [], id="directory-without-file"
        ),
        pytest.param(
            ["homeassistant/components/Peblar/sensor.py"], [], id="not-a-domain"
        ),
    ],
)
def test_touched_domains(filenames: list[str], expected: list[str]) -> None:
    """Only integration paths yield a domain, deduplicated and sorted."""
    assert integrations.touched_domains(filenames) == expected


@pytest.fixture
def components_dir(tmp_path: Path) -> Path:
    """Return a components directory where only peblar has a quality scale."""
    (tmp_path / "peblar").mkdir()
    (tmp_path / "peblar" / "quality_scale.yaml").write_text("rules: {}")
    (tmp_path / "adax").mkdir()
    return tmp_path


def test_keeps_only_domains_that_have_a_quality_scale(components_dir: Path) -> None:
    """A domain without a quality_scale.yaml is not reviewed."""
    assert integrations.with_quality_scale(["adax", "peblar"], [], components_dir) == [
        "peblar"
    ]


def test_keeps_a_quality_scale_the_pull_request_adds(components_dir: Path) -> None:
    """The checkout predates the pull request, so an added file counts too."""
    assert integrations.with_quality_scale(
        ["adax", "peblar"],
        ["homeassistant/components/adax/quality_scale.yaml"],
        components_dir,
    ) == ["adax", "peblar"]


def test_ignores_a_quality_scale_added_for_an_untouched_domain(
    components_dir: Path,
) -> None:
    """Only domains the pull request touches are considered."""
    assert integrations.with_quality_scale(
        ["peblar"],
        ["homeassistant/components/adax/quality_scale.yaml"],
        components_dir,
    ) == ["peblar"]


def test_a_quality_scale_outside_components_does_not_count(
    components_dir: Path,
) -> None:
    """A file merely named quality_scale.yaml elsewhere is not an integration's."""
    assert (
        integrations.with_quality_scale(
            ["adax"], ["script/quality_scale.yaml"], components_dir
        )
        == []
    )
