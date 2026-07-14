"""Runtime counterpart to the missing-feature-implementation pylint checker.

The static checker can only inspect ``_attr_supported_features`` when it is a
literal flag combination. The (very common) pattern of computing the feature
set from device capabilities in ``__init__`` is invisible to it. Once an entity
is *instantiated*, though, ``entity.supported_features`` is a concrete value
regardless of how it was built -- so a runtime check sees exactly the dynamic
declarations the static one throws away.

This module provides:

* ``check_entity(entity, domain)`` -- returns the features an instance
  advertises but does not implement, reusing the *same* fallback-aware feature
  -> method map the pylint checker derives (so climate ``TURN_ON`` etc. are not
  false-positived).
* ``collect_via_add_hook()`` -- a context manager that patches
  ``EntityPlatform._async_add_entity`` so every entity added during a test run
  is checked, accumulating violations. It is wired as an autouse fixture in
  ``tests/components/conftest.py``, sweeping whatever entities the component
  test suite instantiates.

Coverage is bounded by what the test suite actually instantiates -- integrations
with thin tests (often the worst offenders) still slip through, which is why
this complements, rather than replaces, the static checker.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from enum import Flag
from functools import cache
import importlib
import traceback
import types

# ``pylint/plugins`` is on sys.path via pyproject ``[tool.pytest] pythonpath``,
# so the checker's fallback-aware map can be reused verbatim.
from pylint_home_assistant.checkers.supported_features import platform_feature_map

from homeassistant.helpers.entity_platform import EntityPlatform

_COMPONENTS_ROOT = "homeassistant.components"

# Existing violations, to be fixed in per-integration follow-up PRs. Each is a
# real bug: the entity advertises the feature, but calling the corresponding
# service raises NotImplementedError. Do not add new entries; fix the entity.
KNOWN_VIOLATIONS: set[tuple[str, str, str]] = {
    ("homeassistant.components.abode.cover.AbodeCover", "cover", "STOP"),
    (
        "homeassistant.components.hdmi_cec.media_player.CecPlayerEntity",
        "media_player",
        "PLAY_MEDIA",
    ),
    (
        "homeassistant.components.homekit_controller.cover.HomeKitWindowCover",
        "cover",
        "CLOSE_TILT",
    ),
    (
        "homeassistant.components.homekit_controller.cover.HomeKitWindowCover",
        "cover",
        "OPEN_TILT",
    ),
    (
        "homeassistant.components.homematicip_cloud.cover.HomematicipGarageDoorModule",
        "cover",
        "SET_POSITION",
    ),
    (
        "homeassistant.components.samsungtv.media_player.SamsungTVDevice",
        "media_player",
        "STOP",
    ),
    ("homeassistant.components.template.cover.StateCoverEntity", "cover", "STOP_TILT"),
    (
        "homeassistant.components.template.cover.TriggerCoverEntity",
        "cover",
        "STOP_TILT",
    ),
    (
        "homeassistant.components.wmspro.cover.WebControlProSlatRotate",
        "cover",
        "STOP_TILT",
    ),
}


@cache
def _feature_enum(domain: str) -> type[Flag] | None:
    """Return the platform's ``<X>EntityFeature`` IntFlag class, if any."""
    try:
        module = importlib.import_module(f"{_COMPONENTS_ROOT}.{domain}")
    except ImportError:
        return None
    for name in dir(module):
        value = getattr(module, name)
        if (
            isinstance(value, type)
            and issubclass(value, Flag)
            and name.endswith("EntityFeature")
        ):
            return value
    return None


def _defining_class(cls: type, method: str) -> type | None:
    """Return the nearest MRO class that defines *method* as a function."""
    for klass in cls.__mro__:
        member = klass.__dict__.get(method)
        if isinstance(member, (types.FunctionType, classmethod, staticmethod)):
            return klass
    return None


def _is_implemented(cls: type, candidates: frozenset[str], domain: str) -> bool:
    """True if any candidate method is defined outside the platform base package."""
    base_pkg = f"{_COMPONENTS_ROOT}.{domain}"
    for candidate in candidates:
        defining = _defining_class(cls, candidate)
        if defining is not None and not (
            defining.__module__ == base_pkg
            or defining.__module__.startswith(f"{base_pkg}.")
        ):
            return True
    return False


def check_entity(entity: object, domain: str) -> list[tuple[str, frozenset[str]]]:
    """Return ``(flag, acceptable_methods)`` for declared-but-unimplemented features."""
    feature_map = platform_feature_map(domain)
    if not feature_map:
        return []
    supported = getattr(entity, "supported_features", None)
    if not supported:
        return []
    supported = int(supported)
    enum = _feature_enum(domain)
    if enum is None:
        return []

    cls = type(entity)
    violations: list[tuple[str, frozenset[str]]] = []
    for flag, units in feature_map.items():
        member = getattr(enum, flag, None)
        if member is None:
            continue
        bit = int(member)
        if supported & bit != bit:
            continue
        violations.extend(
            (flag, methods)
            for methods in units
            if not _is_implemented(cls, methods, domain)
        )
    return violations


@contextmanager
def collect_via_add_hook(
    module_prefixes: tuple[str, ...] = (f"{_COMPONENTS_ROOT}.",),
) -> Iterator[list[dict]]:
    """Patch entity addition to collect feature-implementation violations.

    Yields a list that fills with one dict per violation as entities are added
    through ``EntityPlatform`` during the ``with`` block. Only entities whose
    class is defined under *module_prefixes* are checked, so test doubles
    defined in test modules are ignored. Group platform entities are exempt:
    service calls targeting a group are expanded to its members, so the group
    never handles them itself. A crash in the probe itself is collected as a
    ``probe_error`` entry rather than swallowed, so the enforcement cannot
    silently stop working.
    """
    collected: list[dict] = []
    seen: set[tuple[str, ...]] = set()
    original = EntityPlatform._async_add_entity

    async def _patched(self, entity, *args, **kwargs):  # type: ignore[no-untyped-def]
        await original(self, entity, *args, **kwargs)
        try:
            cls = type(entity)
            if not cls.__module__.startswith(module_prefixes):
                return
            if cls.__module__.startswith(f"{_COMPONENTS_ROOT}.group."):
                return
            class_name = f"{cls.__module__}.{cls.__qualname__}"
            for flag, methods in check_entity(entity, self.domain):
                if (class_name, self.domain, flag) in KNOWN_VIOLATIONS:
                    continue
                key = (class_name, self.domain, flag, *sorted(methods))
                if key in seen:
                    continue
                seen.add(key)
                collected.append(
                    {
                        "entity_class": class_name,
                        "domain": self.domain,
                        "feature": flag,
                        "methods": sorted(methods),
                    }
                )
        except Exception:  # noqa: BLE001 - surfaced via a probe_error entry
            error = traceback.format_exc()
            if ("probe_error", error) not in seen:
                seen.add(("probe_error", error))
                collected.append({"probe_error": error})

    EntityPlatform._async_add_entity = _patched  # type: ignore[method-assign]
    try:
        yield collected
    finally:
        EntityPlatform._async_add_entity = original  # type: ignore[method-assign]
