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


_ADAX = "homeassistant/components/adax/quality_scale.yaml"
_PEBLAR = "homeassistant/components/peblar/quality_scale.yaml"


@pytest.mark.parametrize(
    ("domains", "file_statuses", "expected"),
    [
        pytest.param(["adax", "peblar"], {}, ["peblar"], id="from-the-checkout"),
        pytest.param(
            ["adax", "peblar"], {_ADAX: "added"}, ["adax", "peblar"], id="added"
        ),
        pytest.param(["peblar"], {_PEBLAR: "modified"}, ["peblar"], id="modified"),
        pytest.param(["adax", "peblar"], {_PEBLAR: "removed"}, [], id="removed"),
        pytest.param(
            ["peblar"], {_ADAX: "added"}, ["peblar"], id="added-for-untouched-domain"
        ),
        pytest.param(
            ["adax"],
            {"script/quality_scale.yaml": "added"},
            [],
            id="outside-components",
        ),
    ],
)
def test_with_quality_scale(
    domains: list[str],
    file_statuses: dict[str, str],
    expected: list[str],
    components_dir: Path,
) -> None:
    """Keep the domains whose quality scale exists at the pull request head.

    The checkout predates the pull request, so its own change to a quality
    scale decides: an added one counts and a removed one does not.
    """
    assert (
        integrations.with_quality_scale(domains, file_statuses, components_dir)
        == expected
    )
