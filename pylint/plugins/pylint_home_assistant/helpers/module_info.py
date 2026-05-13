"""Helpers for parsing integration module paths."""

from dataclasses import dataclass
import re

_INTEGRATION_ROOT = "homeassistant.components"
_INTEGRATION_ROOT_DOT = f"{_INTEGRATION_ROOT}."
_ROOT_SEGMENT_COUNT = _INTEGRATION_ROOT.count(".") + 1
_MODULE_REGEX: re.Pattern[str] = re.compile(
    rf"^{re.escape(_INTEGRATION_ROOT)}\.\w+(\.\w+)?$"
)


@dataclass(frozen=True, slots=True)
class IntegrationModule:
    """Parsed integration module path."""

    root: str
    """The integration root, e.g. ``homeassistant.components``."""
    domain: str
    """The integration domain, e.g. ``hue``."""
    module: str | None
    """The sub-module name, e.g. ``sensor``, ``config_flow``, ``const``.

    ``None`` when the module is the integration's ``__init__``.
    """


def parse_module(module_name: str) -> IntegrationModule | None:
    """Parse a dotted module name into integration parts.

    Returns ``None`` if *module_name* is not under the integration root.
    For deep sub-modules (e.g. ``homeassistant.components.hue.light.v2``),
    ``module`` is set to the first segment after the domain (``light``).
    """
    if not module_name.startswith(_INTEGRATION_ROOT_DOT):
        return None

    parts = module_name.split(".")
    n = len(parts)
    if n < _ROOT_SEGMENT_COUNT + 1:
        return None
    if n == _ROOT_SEGMENT_COUNT + 1:
        return IntegrationModule(
            root=_INTEGRATION_ROOT,
            domain=parts[_ROOT_SEGMENT_COUNT],
            module=None,
        )
    # n >= _ROOT_SEGMENT_COUNT + 2: domain.module[.submodule...]
    return IntegrationModule(
        root=_INTEGRATION_ROOT,
        domain=parts[_ROOT_SEGMENT_COUNT],
        module=parts[_ROOT_SEGMENT_COUNT + 1],
    )


def is_integration_module(module_name: str) -> bool:
    """Return True if *module_name* is under the integration root."""
    return module_name.startswith(_INTEGRATION_ROOT_DOT)


def get_module_platform(module_name: str) -> str | None:
    """Return the platform for the module name.

    Returns ``"__init__"`` for the integration's root module,
    the platform name for a sub-module, or ``None`` if not matched.
    """
    if not (module_match := _MODULE_REGEX.match(module_name)):
        return None
    platform = module_match.group(1)
    return platform.lstrip(".") if platform else "__init__"


def is_test_module(module_name: str) -> bool:
    """Return True if *module_name* is a test module."""
    return module_name.startswith("tests.")
