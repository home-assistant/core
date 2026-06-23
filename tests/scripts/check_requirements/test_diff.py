"""Tests for script.check_requirements.diff."""

import pytest

from script.check_requirements.diff import parse_diff


@pytest.mark.parametrize(
    ("diff_text", "expected"),
    [
        pytest.param(
            (
                "diff --git a/requirements_all.txt b/requirements_all.txt\n"
                "--- a/requirements_all.txt\n"
                "+++ b/requirements_all.txt\n"
                "@@ -1,2 +1,2 @@\n"
                " keep==1.0.0\n"
                "-bumped==1.2.3\n"
                "+bumped==1.3.0\n"
            ),
            [("bumped", "1.2.3", "1.3.0")],
            id="single-bump",
        ),
        pytest.param(
            (
                "diff --git a/requirements_all.txt b/requirements_all.txt\n"
                "--- a/requirements_all.txt\n"
                "+++ b/requirements_all.txt\n"
                "@@ -1 +1,2 @@\n"
                " keep==1.0.0\n"
                "+brand-new==4.5.6\n"
            ),
            [("brand-new", None, "4.5.6")],
            id="single-new",
        ),
        pytest.param(
            (
                "diff --git a/README.md b/README.md\n"
                "--- a/README.md\n"
                "+++ b/README.md\n"
                "@@ -1 +1 @@\n"
                "-some-pkg==1.0.0\n"
                "+some-pkg==2.0.0\n"
            ),
            [],
            id="non-tracked-file-ignored",
        ),
        pytest.param(
            (
                "diff --git a/requirements.txt b/requirements.txt\n"
                "--- a/requirements.txt\n"
                "+++ b/requirements.txt\n"
                "@@ -1 +1 @@\n"
                "-Foo_Bar==1.0\n"
                "+foo-bar==1.1\n"
            ),
            [("foo-bar", "1.0", "1.1")],
            id="pep503-normalisation",
        ),
        pytest.param(
            (
                "diff --git a/requirements_test.txt b/requirements_test.txt\n"
                "--- a/requirements_test.txt\n"
                "+++ b/requirements_test.txt\n"
                "@@ -1 +1 @@\n"
                "-tool==1.0.0\n"
                "+tool==1.0.0\n"
            ),
            [],
            id="no-version-change-ignored",
        ),
        pytest.param(
            (
                "diff --git a/requirements_extra.txt b/requirements_extra.txt\n"
                "--- a/requirements_extra.txt\n"
                "+++ b/requirements_extra.txt\n"
                "@@ -1 +1 @@\n"
                "-pkg==1.0.0\n"
                "+pkg==2.0.0\n"
            ),
            [("pkg", "1.0.0", "2.0.0")],
            id="wildcard-matched-requirements-file",
        ),
        pytest.param(
            (
                "diff --git a/pyproject.toml b/pyproject.toml\n"
                "--- a/pyproject.toml\n"
                "+++ b/pyproject.toml\n"
                "@@ -1 +1 @@\n"
                '-    "requests==1.0.0",\n'
                '+    "requests==2.0.0",\n'
            ),
            [],
            id="pyproject-toml-not-tracked",
        ),
        pytest.param(
            (
                "diff --git a/requirements_all.txt b/requirements_all.txt\n"
                "--- a/requirements_all.txt\n"
                "+++ b/requirements_all.txt\n"
                "@@ -1 +1 @@\n"
                "-# pkg==1.0.0 was bumped\n"
                "+# pkg==2.0.0 was bumped\n"
            ),
            [],
            id="comment-lines-skipped",
        ),
        pytest.param(
            (
                "diff --git a/requirements_all.txt b/requirements_all.txt\n"
                "--- a/requirements_all.txt\n"
                "+++ b/requirements_all.txt\n"
                "@@ -1 +1 @@\n"
                "-pkg==1.0.0  # old\n"
                "+pkg==2.0.0  # new\n"
            ),
            [("pkg", "1.0.0", "2.0.0")],
            id="inline-comment-stripped",
        ),
    ],
)
def test_parse_diff(
    diff_text: str,
    expected: list[tuple[str, str | None, str]],
) -> None:
    """Test that parse_diff extracts the expected package changes."""
    changes = parse_diff(diff_text)
    actual = [(c.name, c.old_version, c.new_version) for c in changes]
    assert actual == expected
