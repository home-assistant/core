"""Tests for the enum_identity_compare mypy plugin.

Each test snippet is run through mypy's API with the plugin enabled. We
assert which line numbers emit the ``ha-enum-identity-compare`` error.

The plugin is intentionally narrow: it fires only on plain ``enum.Enum``
subclasses (where ``__eq__`` is identity-based) plus a small allowlist
of HA-framework-controlled ``StrEnum`` classes. Generic StrEnum/IntEnum
are deliberately skipped — see the plugin module docstring.
"""

import os
from pathlib import Path
import sys
import textwrap

from mypy import api as mypy_api

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PLUGINS_ROOT = _PROJECT_ROOT  # mypy_plugins/ lives under the worktree root


def _run_mypy(code: str, tmp_path: Path) -> list[str]:
    """Run mypy with the plugin and return ha-enum-identity-compare errors.

    Each error is normalized to ``LINE: MESSAGE`` form.
    """
    src = tmp_path / "case.py"
    src.write_text(textwrap.dedent(code))
    config = tmp_path / "mypy.ini"
    config.write_text(
        "[mypy]\n"
        "plugins = mypy_plugins.enum_identity_compare\n"
        "show_error_codes = true\n"
        "strict_equality = true\n"
    )

    env_pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = f"{_PLUGINS_ROOT}{os.pathsep}{env_pythonpath}"
    # Make sure mypy can import the plugin from the current process.
    sys.path.insert(0, str(_PLUGINS_ROOT))
    try:
        # mypy ships as a compiled extension; pylint can't introspect it.
        stdout, _stderr, _rc = mypy_api.run(  # pylint: disable=c-extension-no-member
            [
                "--no-incremental",
                "--cache-dir=/dev/null",
                "--config-file",
                str(config),
                str(src),
            ]
        )
    finally:
        os.environ["PYTHONPATH"] = env_pythonpath
        sys.path.pop(0)

    errors: list[str] = []
    for line in stdout.splitlines():
        if "[ha-enum-identity-compare]" not in line:
            continue
        # Format: "<path>:<line>: error: <msg>  [code]"
        prefix, _, msg = line.partition(": error: ")
        line_no = prefix.rsplit(":", 1)[-1].strip()
        msg_clean = msg.split("  [ha-enum-identity-compare]", 1)[0].strip()
        errors.append(f"{line_no}: {msg_clean}")
    return errors


_PRELUDE = """
from enum import Enum, IntEnum, IntFlag, StrEnum

class ConfigEntryState(Enum):
    LOADED = "loaded"
    NOT_LOADED = "not_loaded"

class MediaType(StrEnum):
    CHANNEL = "channel"
    APP = "app"

class HTTPStatus(IntEnum):
    OK = 200

class ClimateFeature(IntFlag):
    SWING_MODE = 32
"""


def test_bad_plain_enum_eq(tmp_path: Path) -> None:
    """`==` on two operands of the same plain ``Enum`` must flag."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(s: ConfigEntryState) -> bool:
    return s == ConfigEntryState.LOADED
""",
        tmp_path,
    )
    assert len(errors) == 1
    assert "ConfigEntryState" in errors[0]
    assert "`is`" in errors[0] and "`==`" in errors[0]


def test_bad_plain_enum_ne(tmp_path: Path) -> None:
    """`!=` on two operands of the same plain ``Enum`` must flag."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(s: ConfigEntryState) -> bool:
    return s != ConfigEntryState.NOT_LOADED
""",
        tmp_path,
    )
    assert len(errors) == 1
    assert "`is not`" in errors[0] and "`!=`" in errors[0]


def test_bad_plain_enum_lhs(tmp_path: Path) -> None:
    """Plain enum on the LHS is also flagged."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(s: ConfigEntryState) -> bool:
    return ConfigEntryState.LOADED == s
""",
        tmp_path,
    )
    assert len(errors) == 1


def test_good_strenum_not_allowlisted(tmp_path: Path) -> None:
    """A StrEnum defined in user code is NOT flagged.

    The plugin can't tell whether callers will pass the enum instance or
    the underlying string (StrEnum's whole point is making both work).
    Allowlisting is required for individual classes.
    """
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(m: MediaType) -> bool:
    return m == MediaType.CHANNEL
""",
        tmp_path,
    )
    assert errors == []


def test_good_intenum_not_allowlisted(tmp_path: Path) -> None:
    """An IntEnum defined in user code is NOT flagged for the same reason."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(code: HTTPStatus) -> bool:
    return code == HTTPStatus.OK
""",
        tmp_path,
    )
    assert errors == []


def test_good_str_vs_strenum(tmp_path: Path) -> None:
    """Comparing a raw `str` against a `StrEnum` member is legitimate."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(raw: str) -> bool:
    return raw == MediaType.CHANNEL
""",
        tmp_path,
    )
    assert errors == []


def test_good_int_vs_intenum(tmp_path: Path) -> None:
    """Comparing a raw `int` against an `IntEnum` member is legitimate."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(code: int) -> bool:
    return code == HTTPStatus.OK
""",
        tmp_path,
    )
    assert errors == []


def test_good_union_with_str(tmp_path: Path) -> None:
    """A union LHS (e.g. ``MediaType | str``) is NOT flagged.

    Even if MediaType were allowlisted, the union means runtime callers
    can pass either form; switching to ``is`` would break the str arm.
    """
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(m: MediaType | str) -> bool:
    return m == MediaType.CHANNEL
""",
        tmp_path,
    )
    assert errors == []


def test_good_intflag_bitwise(tmp_path: Path) -> None:
    """``IntFlag`` bitwise ``==`` is the standard pattern."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(features: ClimateFeature) -> bool:
    return features & ClimateFeature.SWING_MODE == ClimateFeature.SWING_MODE
""",
        tmp_path,
    )
    assert errors == []


def test_good_is_already(tmp_path: Path) -> None:
    """``is`` is the recommended form — must not fire on itself."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(s: ConfigEntryState) -> bool:
    return s is ConfigEntryState.LOADED
""",
        tmp_path,
    )
    assert errors == []


def test_good_unrelated_compare(tmp_path: Path) -> None:
    """Plain ``int`` ``==`` ``int`` (no enum involved) must not flag."""
    errors = _run_mypy(
        _PRELUDE + "\nif 1 == 2:\n    pass\n",
        tmp_path,
    )
    assert errors == []


def test_good_ordering_op(tmp_path: Path) -> None:
    """Ordering comparison (``>``) on an enum must not flag."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(s: HTTPStatus) -> bool:
    return s > HTTPStatus.OK
""",
        tmp_path,
    )
    assert errors == []
