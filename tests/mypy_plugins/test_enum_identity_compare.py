"""Tests for the enum_identity_compare mypy plugin.

Each test snippet is run through mypy's API with the plugin enabled. We
assert which line numbers emit the ``ha-enum-identity-compare`` error.
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
    config.write_text("[mypy]\nplugins = mypy_plugins.enum_identity_compare\n")

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


# ============================================================
# Common fixture code prepended to each snippet for type definitions
# ============================================================
_PRELUDE = """
from enum import Enum, IntEnum, IntFlag, StrEnum
from typing import TypedDict

class FlowResultType(StrEnum):
    FORM = "form"
    ABORT = "abort"

class ConfigEntryState(Enum):
    LOADED = "loaded"
    NOT_LOADED = "not_loaded"

class HTTPStatus(IntEnum):
    OK = 200

class ClimateFeature(IntFlag):
    SWING_MODE = 32

class FlowResult(TypedDict, total=False):
    type: FlowResultType
"""


def test_bad_strenum_eq(tmp_path: Path) -> None:
    """`==` on two operands of the same ``StrEnum`` must flag."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(t: FlowResultType) -> bool:
    return t == FlowResultType.FORM
""",
        tmp_path,
    )
    assert len(errors) == 1
    assert "FlowResultType" in errors[0]
    assert "`is`" in errors[0] and "`==`" in errors[0]


def test_bad_strenum_ne(tmp_path: Path) -> None:
    """`!=` on two operands of the same ``StrEnum`` must flag."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(t: FlowResultType) -> bool:
    return t != FlowResultType.ABORT
""",
        tmp_path,
    )
    assert len(errors) == 1
    assert "`is not`" in errors[0] and "`!=`" in errors[0]


def test_bad_plain_enum(tmp_path: Path) -> None:
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


def test_bad_intenum(tmp_path: Path) -> None:
    """`==` on two operands of the same ``IntEnum`` must flag."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(s: HTTPStatus) -> bool:
    return s == HTTPStatus.OK
""",
        tmp_path,
    )
    assert len(errors) == 1
    assert "HTTPStatus" in errors[0]


def test_bad_typeddict_subscript(tmp_path: Path) -> None:
    """Mypy's killer feature: tracking through a TypedDict subscript."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(result: FlowResult) -> bool:
    return result["type"] == FlowResultType.FORM
""",
        tmp_path,
    )
    assert len(errors) == 1
    assert "FlowResultType" in errors[0]


def test_good_str_vs_strenum(tmp_path: Path) -> None:
    """Comparing a `str` against a `StrEnum` member is legitimate."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(raw: str) -> bool:
    return raw == FlowResultType.FORM
""",
        tmp_path,
    )
    assert errors == []


def test_good_int_vs_intenum(tmp_path: Path) -> None:
    """Comparing an `int` against an `IntEnum` member is legitimate."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(code: int) -> bool:
    return code == HTTPStatus.OK
""",
        tmp_path,
    )
    assert errors == []


def test_good_intflag_bitwise(tmp_path: Path) -> None:
    """IntFlag bitwise == is the standard pattern."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(features: int) -> bool:
    return features & ClimateFeature.SWING_MODE == ClimateFeature.SWING_MODE
""",
        tmp_path,
    )
    assert errors == []


def test_good_is_already(tmp_path: Path) -> None:
    """`is` is the recommended form — must not fire on itself."""
    errors = _run_mypy(
        _PRELUDE
        + """
def fn(t: FlowResultType) -> bool:
    return t is FlowResultType.FORM
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
