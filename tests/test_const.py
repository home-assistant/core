"""Test const module."""

from enum import Enum
import logging
import sys
from unittest.mock import Mock, patch

import pytest

from homeassistant import const
from homeassistant.components import alarm_control_panel, lock

from .common import (
    extract_stack_to_frame,
    help_test_all,
    import_and_test_deprecated_constant,
    import_and_test_deprecated_constant_enum,
)


def _create_tuples(
    value: type[Enum] | list[Enum], constant_prefix: str
) -> list[tuple[Enum, str]]:
    return [(enum, constant_prefix) for enum in value]


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(const)


@pytest.mark.parametrize(
    ("replacement", "constant_name", "breaks_in_version"),
    [
        (const.UnitOfArea.SQUARE_METERS, "AREA_SQUARE_METERS", "2025.12"),
    ],
)
def test_deprecated_constant_name_changes(
    caplog: pytest.LogCaptureFixture,
    replacement: Enum,
    constant_name: str,
    breaks_in_version: str,
) -> None:
    """Test deprecated constants, where the name is not the same as the enum value."""
    import_and_test_deprecated_constant(
        caplog,
        const,
        constant_name,
        f"{replacement.__class__.__name__}.{replacement.name}",
        replacement,
        breaks_in_version,
    )


def _create_tuples_lock_states(
    enum: type[Enum], constant_prefix: str, remove_in_version: str
) -> list[tuple[Enum, str]]:
    return [
        (enum_field, constant_prefix, remove_in_version)
        for enum_field in enum
        if enum_field
        not in [
            lock.LockState.OPEN,
            lock.LockState.OPENING,
        ]
    ]


@pytest.mark.parametrize(
    ("enum", "constant_prefix", "remove_in_version"),
    _create_tuples_lock_states(lock.LockState, "STATE_", "2025.10"),
)
def test_deprecated_constants_lock(
    caplog: pytest.LogCaptureFixture,
    enum: Enum,
    constant_prefix: str,
    remove_in_version: str,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, const, enum, constant_prefix, remove_in_version
    )


def _create_tuples_alarm_states(
    enum: type[Enum], constant_prefix: str, remove_in_version: str
) -> list[tuple[Enum, str]]:
    return [
        (enum_field, constant_prefix, remove_in_version)
        for enum_field in enum
        if enum_field
        not in [
            lock.LockState.OPEN,
            lock.LockState.OPENING,
        ]
    ]


@pytest.mark.parametrize(
    ("enum", "constant_prefix", "remove_in_version"),
    _create_tuples_lock_states(
        alarm_control_panel.AlarmControlPanelState, "STATE_ALARM_", "2025.11"
    ),
)
def test_deprecated_constants_alarm(
    caplog: pytest.LogCaptureFixture,
    enum: Enum,
    constant_prefix: str,
    remove_in_version: str,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, const, enum, constant_prefix, remove_in_version
    )


def test_deprecated_unit_of_conductivity_alias() -> None:
    """Test UnitOfConductivity deprecation."""

    # Test the deprecated members are aliases
    assert set(const.UnitOfConductivity) == {"S/cm", "µS/cm", "mS/cm"}


def test_deprecated_unit_of_conductivity_members(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test UnitOfConductivity deprecation."""

    module_name = "config.custom_components.hue.light"
    filename = f"/home/paulus/{module_name.replace('.', '/')}.py"

    with (
        patch.dict(sys.modules, {module_name: Mock(__file__=filename)}),
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.close()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    Mock(
                        filename=filename,
                        lineno="23",
                        line="await session.close()",
                    ),
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        const.UnitOfConductivity.SIEMENS  # noqa: B018
        const.UnitOfConductivity.MICROSIEMENS  # noqa: B018
        const.UnitOfConductivity.MILLISIEMENS  # noqa: B018

    assert len(caplog.record_tuples) == 3

    def deprecation_message(member: str, replacement: str) -> str:
        return (
            f"UnitOfConductivity.{member} was used from hue, this is a deprecated enum "
            "member which will be removed in HA Core 2025.11.0. Use UnitOfConductivity."
            f"{replacement} instead, please report it to the author of the 'hue' custom"
            " integration"
        )

    assert (
        const.__name__,
        logging.WARNING,
        deprecation_message("SIEMENS", "SIEMENS_PER_CM"),
    ) in caplog.record_tuples
    assert (
        const.__name__,
        logging.WARNING,
        deprecation_message("MICROSIEMENS", "MICROSIEMENS_PER_CM"),
    ) in caplog.record_tuples
    assert (
        const.__name__,
        logging.WARNING,
        deprecation_message("MILLISIEMENS", "MILLISIEMENS_PER_CM"),
    ) in caplog.record_tuples
