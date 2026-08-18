"""Tests for the enum_identity_compare mypy plugin.

Each test snippet is run through mypy's API with the plugin enabled.
Tests assert the number of ``home-assistant-enum-identity-compare`` errors emitted
and the relevant message content (operator pair and enum class name).

The plugin is intentionally narrow: it fires only on plain ``enum.Enum``
subclasses (where ``__eq__`` is identity-based) plus a small set of
framework-guaranteed ``StrEnum`` classes. Generic StrEnum/IntEnum are
deliberately skipped — see the plugin module docstring.
"""

import os
from pathlib import Path
import sys
import textwrap

from mypy import api as mypy_api
import pytest

_IS_EQ = ("`is`", "`==`")
_IS_NOT_NE = ("`is not`", "`!=`")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PLUGINS_ROOT = _PROJECT_ROOT  # mypy_plugins/ lives under the worktree root


def _run_mypy(code: str, tmp_path: Path, mypy_path: str | None = None) -> list[str]:
    """Run mypy with the plugin and return home-assistant-enum-identity-compare errors.

    Each error is normalized to ``LINE: MESSAGE`` form. ``mypy_path``, if
    given, is written into ``mypy.ini`` so tests can supply stub modules
    that resolve to specific fullnames (used for the framework-guaranteed set).
    """
    src = tmp_path / "case.py"
    src.write_text(textwrap.dedent(code))
    cache = tmp_path / "mypy_cache"
    config = tmp_path / "mypy.ini"
    config_body = (
        "[mypy]\n"
        "plugins = mypy_plugins.enum_identity_compare\n"
        "show_error_codes = true\n"
        "strict_equality = true\n"
    )
    if mypy_path is not None:
        config_body += f"mypy_path = {mypy_path}\n"
    config.write_text(config_body)

    env_pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = f"{_PLUGINS_ROOT}{os.pathsep}{env_pythonpath}"
    # Make sure mypy can import the plugin from the current process.
    sys.path.insert(0, str(_PLUGINS_ROOT))
    try:
        # mypy ships as a compiled extension; pylint can't introspect it.
        stdout, _stderr, _rc = mypy_api.run(  # pylint: disable=c-extension-no-member
            [
                "--no-incremental",
                f"--cache-dir={cache}",
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
        if "[home-assistant-enum-identity-compare]" not in line:
            continue
        # Format: "<path>:<line>: error: <msg>  [code]"
        prefix, _, msg = line.partition(": error: ")
        line_no = prefix.rsplit(":", 1)[-1].strip()
        msg_clean = msg.split("  [home-assistant-enum-identity-compare]", 1)[0].strip()
        errors.append(f"{line_no}: {msg_clean}")
    return errors


_PRELUDE = """
import dataclasses
from enum import Enum, IntEnum, IntFlag, StrEnum
from typing import NamedTuple

class ConfigEntryState(Enum):
    LOADED = "loaded"
    NOT_LOADED = "not_loaded"

class SourceCodes(Enum):
    DAB = "dab"
    FM = "fm"
    AUX = "aux"

class MediaType(StrEnum):
    CHANNEL = "channel"
    APP = "app"

class HTTPStatus(IntEnum):
    OK = 200

class ClimateFeature(IntFlag):
    SWING_MODE = 32

class AudioBitRates(int, Enum):
    BITRATE_8 = 8
    BITRATE_16 = 16

class LegacyStr(str, Enum):
    A = "a"
    B = "b"

class HomeeCoverState(float, Enum):
    OPEN = 0.0
    CLOSED = 1.0

class LegacyBytes(bytes, Enum):
    A = b"a"
    B = b"b"

@dataclasses.dataclass(frozen=True)
class _VariantInfo:
    label: str

class HardwareVariant(_VariantInfo, Enum):
    A = ("a",)
    B = ("b",)

class _NamedVariant(NamedTuple):
    label: str

class NamedTupleEnum(_NamedVariant, Enum):
    A = ("a",)
    B = ("b",)

class _BaseStates(Enum):
    pass

class DerivedStates(_BaseStates):
    ON = 1
    OFF = 2
"""


@pytest.mark.parametrize(
    ("snippet", "enum_name", "op_substrings"),
    [
        pytest.param(
            """
def fn(s: ConfigEntryState) -> bool:
    return s == ConfigEntryState.LOADED
""",
            "ConfigEntryState",
            _IS_EQ,
            id="plain_enum_eq",
        ),
        pytest.param(
            """
def fn(s: ConfigEntryState) -> bool:
    return s != ConfigEntryState.NOT_LOADED
""",
            "ConfigEntryState",
            _IS_NOT_NE,
            id="plain_enum_ne",
        ),
        pytest.param(
            """
def fn(s: ConfigEntryState) -> bool:
    return ConfigEntryState.LOADED == s
""",
            "ConfigEntryState",
            _IS_EQ,
            id="plain_enum_lhs",
        ),
        # An ``elif`` after an ``is`` check narrows the LHS to a literal
        # union. Without union/literal handling, the plugin would silently
        # skip the ``==`` even though both operands resolve to ``SourceCodes``.
        pytest.param(
            """
def fn(source: SourceCodes) -> str:
    if source is SourceCodes.DAB:
        return "dab"
    elif source == SourceCodes.FM:
        return "fm"
    return "other"
""",
            "SourceCodes",
            _IS_EQ,
            id="narrowed_elif",
        ),
        pytest.param(
            """
from typing import Literal

def fn(s: Literal[ConfigEntryState.LOADED]) -> bool:
    return s == ConfigEntryState.LOADED
""",
            "ConfigEntryState",
            _IS_EQ,
            id="literal_annotation",
        ),
        # ``Enum | None == Enum``: the plugin conservatively rejects any union
        # containing ``None``, but under ``strict_equality`` mypy narrows the
        # LHS to the enum class before invoking ``__eq__``, so this call site
        # never reaches the union path and is correctly flagged. HA's
        # ``mypy.ini`` sets ``strict_equality``.
        pytest.param(
            """
def fn(source: SourceCodes | None) -> bool:
    return source == SourceCodes.DAB
""",
            "SourceCodes",
            _IS_EQ,
            id="optional_enum_under_strict_equality",
        ),
        # An enum deriving from an intermediate ``Enum`` base (no data mixin)
        # is still identity-based and must be flagged — the structural check
        # must not mistake the intermediate base for a value mixin.
        pytest.param(
            """
def fn(s: DerivedStates) -> bool:
    return s == DerivedStates.ON
""",
            "DerivedStates",
            _IS_EQ,
            id="derived_from_intermediate_enum_base",
        ),
    ],
)
def test_bad_plain_enum(
    tmp_path: Path,
    snippet: str,
    enum_name: str,
    op_substrings: tuple[str, str],
) -> None:
    """Comparisons on plain ``Enum`` operands must flag a single error."""
    errors = _run_mypy(_PRELUDE + snippet, tmp_path)
    assert len(errors) == 1
    assert enum_name in errors[0]
    assert all(op in errors[0] for op in op_substrings)


@pytest.mark.parametrize(
    "snippet",
    [
        # A StrEnum defined in user code is NOT flagged: the plugin can't tell
        # whether callers pass the enum instance or the underlying string
        # (StrEnum's whole point is making both work). It must be added to
        # ``_FRAMEWORK_GUARANTEED_ENUMS`` to be checked.
        pytest.param(
            """
def fn(m: MediaType) -> bool:
    return m == MediaType.CHANNEL
""",
            id="strenum_not_framework_guaranteed",
        ),
        # An IntEnum defined in user code is NOT flagged for the same reason.
        pytest.param(
            """
def fn(code: HTTPStatus) -> bool:
    return code == HTTPStatus.OK
""",
            id="intenum_not_framework_guaranteed",
        ),
        # The legacy ``(int, Enum)`` mixin inherits a value-based ``__eq__``
        # from ``int`` (no ``enum.IntEnum`` base), so it is NOT flagged either.
        pytest.param(
            """
def fn(rate: AudioBitRates) -> bool:
    return rate == AudioBitRates.BITRATE_8
""",
            id="int_enum_mixin_not_framework_guaranteed",
        ),
        # And the same for the legacy ``(str, Enum)`` mixin.
        pytest.param(
            """
def fn(v: LegacyStr) -> bool:
    return v == LegacyStr.A
""",
            id="str_enum_mixin_not_framework_guaranteed",
        ),
        # A ``(float, Enum)`` mixin is value-based too (``__eq__`` from float).
        pytest.param(
            """
def fn(s: HomeeCoverState) -> bool:
    return s == HomeeCoverState.OPEN
""",
            id="float_enum_mixin_not_framework_guaranteed",
        ),
        # And a ``(bytes, Enum)`` mixin likewise.
        pytest.param(
            """
def fn(v: LegacyBytes) -> bool:
    return v == LegacyBytes.A
""",
            id="bytes_enum_mixin_not_framework_guaranteed",
        ),
        # A ``@dataclass`` mixin is value-based (generated ``__eq__`` compares
        # by value), even though the mixin is not a builtin primitive.
        pytest.param(
            """
def fn(v: HardwareVariant) -> bool:
    return v == HardwareVariant.A
""",
            id="dataclass_mixin_not_flagged",
        ),
        # A ``NamedTuple`` mixin is value-based too (tuple ``__eq__``).
        pytest.param(
            """
def fn(v: NamedTupleEnum) -> bool:
    return v == NamedTupleEnum.A
""",
            id="namedtuple_mixin_not_flagged",
        ),
        # Comparing a raw ``str`` against a ``StrEnum`` member is legitimate.
        pytest.param(
            """
def fn(raw: str) -> bool:
    return raw == MediaType.CHANNEL
""",
            id="str_vs_strenum",
        ),
        # Comparing a raw ``int`` against an ``IntEnum`` member is legitimate.
        pytest.param(
            """
def fn(code: int) -> bool:
    return code == HTTPStatus.OK
""",
            id="int_vs_intenum",
        ),
        # A union LHS (e.g. ``MediaType | str``) is NOT flagged: even if
        # MediaType were framework-guaranteed, runtime callers can pass either form, so
        # switching to ``is`` would break the str arm.
        pytest.param(
            """
def fn(m: MediaType | str) -> bool:
    return m == MediaType.CHANNEL
""",
            id="union_with_str",
        ),
        # ``IntFlag`` bitwise ``==`` is the standard pattern.
        pytest.param(
            """
def fn(features: ClimateFeature) -> bool:
    return features & ClimateFeature.SWING_MODE == ClimateFeature.SWING_MODE
""",
            id="intflag_bitwise",
        ),
        # ``is`` is the recommended form — must not fire on itself.
        pytest.param(
            """
def fn(s: ConfigEntryState) -> bool:
    return s is ConfigEntryState.LOADED
""",
            id="is_already",
        ),
        # ``is not`` is the recommended negative form — must not fire on itself.
        pytest.param(
            """
def fn(s: ConfigEntryState) -> bool:
    return s is not ConfigEntryState.LOADED
""",
            id="is_not_already",
        ),
        # Plain ``int`` ``==`` ``int`` (no enum involved) must not flag.
        pytest.param(
            "\nif 1 == 2:\n    pass\n",
            id="unrelated_compare",
        ),
        # Ordering comparison (``>``) on an enum must not flag.
        pytest.param(
            """
def fn(s: HTTPStatus) -> bool:
    return s > HTTPStatus.OK
""",
            id="ordering_op",
        ),
    ],
)
def test_good_no_flag(tmp_path: Path, snippet: str) -> None:
    """Legitimate comparisons must not emit any error."""
    errors = _run_mypy(_PRELUDE + snippet, tmp_path)
    assert errors == []


def _write_flow_result_type_stub(tmp_path: Path) -> None:
    """Write a fake ``homeassistant.data_entry_flow`` module under tmp_path.

    ``_FRAMEWORK_GUARANTEED_ENUMS`` matches by fullname
    (``homeassistant.data_entry_flow.FlowResultType``), so we synthesize a
    package at that path rather than depending on the real HA tree being
    importable from the test environment.
    """
    pkg = tmp_path / "homeassistant"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "data_entry_flow.py").write_text(
        "from enum import StrEnum\n"
        "class FlowResultType(StrEnum):\n"
        '    FORM = "form"\n'
        '    ABORT = "abort"\n'
    )


@pytest.mark.parametrize(
    ("snippet", "op_substrings"),
    [
        # ``FlowResultType`` is on ``_FRAMEWORK_GUARANTEED_ENUMS`` and must
        # flag. StrEnum normally escapes the plugin, but this class is
        # explicitly included because HA's framework controls every
        # value-assigning callsite — see the plugin module docstring.
        pytest.param(
            """
from homeassistant.data_entry_flow import FlowResultType

def fn(r: FlowResultType) -> bool:
    return r == FlowResultType.FORM
""",
            _IS_EQ,
            id="eq",
        ),
        # And the same for ``!=`` against the framework-guaranteed ``FlowResultType``.
        pytest.param(
            """
from homeassistant.data_entry_flow import FlowResultType

def fn(r: FlowResultType) -> bool:
    return r != FlowResultType.ABORT
""",
            _IS_NOT_NE,
            id="ne",
        ),
    ],
)
def test_bad_framework_guaranteed(
    tmp_path: Path,
    snippet: str,
    op_substrings: tuple[str, str],
) -> None:
    """The framework-guaranteed ``FlowResultType`` StrEnum must flag a single error."""
    _write_flow_result_type_stub(tmp_path)
    errors = _run_mypy(snippet, tmp_path, mypy_path=str(tmp_path))
    assert len(errors) == 1
    assert "FlowResultType" in errors[0]
    assert all(op in errors[0] for op in op_substrings)
