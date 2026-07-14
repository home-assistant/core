"""Tests for pylint home-assistant-missing-feature-implementation checker.

These exercise the checker against the *real* platform base classes so that
both the runtime feature->method extraction and the implementation lookup are
covered end to end.
"""

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from . import assert_no_messages, walk_checker

_MSG = "home-assistant-missing-feature-implementation"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    class MyCover(CoverEntity):
        _attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

        async def async_open_cover(self, **kwargs):
            pass

        async def async_close_cover(self, **kwargs):
            pass
    """,
            id="cover_implements_async",
        ),
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    class MyCover(CoverEntity):
        _attr_supported_features = CoverEntityFeature.OPEN

        def open_cover(self, **kwargs):
            pass
    """,
            id="cover_implements_sync_counterpart",
        ),
        pytest.param(
            """
    from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature

    class MyVacuum(StateVacuumEntity):
        def __init__(self):
            self._attr_supported_features = VacuumEntityFeature.START

        async def async_start(self):
            pass
    """,
            id="vacuum_declared_in_init_implemented",
        ),
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    class MyCover(CoverEntity):
        @property
        def supported_features(self):
            return CoverEntityFeature.OPEN
    """,
            id="dynamic_property_is_skipped",
        ),
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity

    class MyCover(CoverEntity):
        _attr_supported_features = SOME_COMPUTED_VALUE
    """,
            id="non_literal_value_is_skipped",
        ),
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    class MyCover(CoverEntity):
        def __init__(self, features):
            self._attr_supported_features = CoverEntityFeature.OPEN
            if features:
                self._attr_supported_features |= CoverEntityFeature.CLOSE
    """,
            id="augmented_assignment_is_skipped",
        ),
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    class MyBaseCover(CoverEntity):
        _attr_supported_features = CoverEntityFeature.OPEN

    class MyCover(MyBaseCover):
        async def async_open_cover(self, **kwargs):
            pass
    """,
            id="same_module_base_is_exempted",
        ),
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    class MyCover(CoverEntity):
        _attr_supported_features = CoverEntityFeature(0)
    """,
            id="no_features_declared",
        ),
        pytest.param(
            """
    from homeassistant.components.valve import ValveEntity, ValveEntityFeature

    class MyValve(ValveEntity):
        _attr_supported_features = ValveEntityFeature.STOP

        def stop_valve(self):
            pass
    """,
            id="valve_base_entity_in_submodule_implemented",
        ),
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    class MyCover(CoverEntity):
        _attr_supported_features = CoverEntityFeature.OPEN

        def __init__(self):
            self._attr_supported_features = self._compute_features()

        def _compute_features(self):
            return CoverEntityFeature(0)
    """,
            id="computed_call_overwrite_is_skipped",
        ),
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    def _features_from_caps():
        return CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    class DynamicCover(CoverEntity):
        def __init__(self):
            self._attr_supported_features = _features_from_caps()

        async def async_open_cover(self, **kwargs):
            ...
    """,
            id="dynamic_call_declaration_is_skipped",
        ),
    ],
)
def test_supported_features_good(
    linter: UnittestLinter,
    enforce_supported_features_checker: BaseChecker,
    code: str,
) -> None:
    """Cases that must not raise a message."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.cover")
    with assert_no_messages(linter):
        walk_checker(linter, enforce_supported_features_checker, root_node)


@pytest.mark.parametrize(
    ("code", "expected_features"),
    [
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    class MyCover(CoverEntity):
        _attr_supported_features = CoverEntityFeature.OPEN
    """,
            {"OPEN"},
            id="cover_missing_open",
        ),
        pytest.param(
            """
    from homeassistant.components.cover import CoverEntity, CoverEntityFeature

    class MyCover(CoverEntity):
        _attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

        async def async_open_cover(self, **kwargs):
            pass
    """,
            {"CLOSE"},
            id="cover_missing_one_of_two",
        ),
        pytest.param(
            """
    from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature

    class MyVacuum(StateVacuumEntity):
        def __init__(self):
            self._attr_supported_features = VacuumEntityFeature.START
    """,
            {"START"},
            id="vacuum_declared_in_init_missing",
        ),
        pytest.param(
            """
    from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature

    class MyClimate(ClimateEntity):
        _attr_supported_features = ClimateEntityFeature.PRESET_MODE
    """,
            {"PRESET_MODE"},
            id="climate_indirection_missing",
        ),
        pytest.param(
            """
    from homeassistant.components.valve import ValveEntity, ValveEntityFeature

    class MyValve(ValveEntity):
        _attr_supported_features = ValveEntityFeature.STOP
    """,
            {"STOP"},
            id="valve_base_entity_in_submodule_missing",
        ),
    ],
)
def test_supported_features_bad(
    linter: UnittestLinter,
    enforce_supported_features_checker: BaseChecker,
    code: str,
    expected_features: set[str],
) -> None:
    """Cases that must raise a message per unimplemented feature."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.cover")
    walk_checker(linter, enforce_supported_features_checker, root_node)
    messages = linter.release_messages()
    assert {msg.args[0] for msg in messages} == expected_features
    assert all(msg.msg_id == _MSG for msg in messages)
