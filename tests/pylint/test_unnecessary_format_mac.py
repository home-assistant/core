"""Tests for the unnecessary format_mac checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.unnecessary_format_mac import (
    UnnecessaryFormatMacChecker,
)
import pytest

from . import assert_no_messages

_IMPORTS = """\
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
"""


@pytest.fixture(name="format_mac_checker")
def format_mac_checker_fixture(
    linter: UnittestLinter,
) -> UnnecessaryFormatMacChecker:
    """Fixture to provide an unnecessary format_mac checker."""
    return UnnecessaryFormatMacChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            f"""
{_IMPORTS}
device = DeviceInfo(
    connections={{(CONNECTION_NETWORK_MAC, mac)}},
)
""",
            id="raw_mac_no_format",
        ),
        pytest.param(
            f"""
{_IMPORTS}
unique_id = format_mac(mac)
""",
            id="format_mac_outside_connection_tuple",
        ),
        pytest.param(
            f"""
{_IMPORTS}
device = DeviceInfo(
    connections={{("other_type", format_mac(mac))}},
)
""",
            id="format_mac_with_non_mac_connection_type",
        ),
        pytest.param(
            f"""
{_IMPORTS}
result = (CONNECTION_NETWORK_MAC, mac, extra)
""",
            id="three_element_tuple",
        ),
        pytest.param(
            f"""
{_IMPORTS}
if (CONNECTION_NETWORK_MAC, format_mac(mac)) in device.connections:
    pass
""",
            id="direct_comparison_in_operator",
        ),
        pytest.param(
            f"""
{_IMPORTS}
valid = {{(CONNECTION_NETWORK_MAC, format_mac(mac))}}
result = device.connections & valid
""",
            id="set_intersection_comparison",
        ),
        pytest.param(
            f"""
{_IMPORTS}
conn = (CONNECTION_NETWORK_MAC, format_mac(mac))
""",
            id="standalone_tuple_not_in_connections_kwarg",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    format_mac_checker: UnnecessaryFormatMacChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.sensor")

    walker = ASTWalker(linter)
    walker.add_checker(format_mac_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            f"""
{_IMPORTS}
device = DeviceInfo(
    connections={{(CONNECTION_NETWORK_MAC, format_mac(mac))}},
)
""",
            id="device_info_connections_kwarg",
        ),
        pytest.param(
            """
import homeassistant.helpers.device_registry as dr
device = dr.DeviceInfo(
    connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))},
)
""",
            id="module_qualified",
        ),
        pytest.param(
            f"""
{_IMPORTS}
device_registry.async_get_or_create(
    config_entry_id=entry.entry_id,
    connections={{(CONNECTION_NETWORK_MAC, format_mac(mac))}},
)
""",
            id="async_get_or_create_connections",
        ),
        pytest.param(
            f"""
{_IMPORTS}
device_registry.async_get_device(
    connections={{(CONNECTION_NETWORK_MAC, format_mac(mac))}},
)
""",
            id="async_get_device_connections",
        ),
    ],
)
def test_format_mac_flagged(
    linter: UnittestLinter,
    format_mac_checker: UnnecessaryFormatMacChecker,
    code: str,
) -> None:
    """Warning when format_mac is used in connections= keyword argument."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.sensor")

    walker = ASTWalker(linter)
    walker.add_checker(format_mac_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-unnecessary-format-mac"


def test_non_integration_module_ignored(
    linter: UnittestLinter,
    format_mac_checker: UnnecessaryFormatMacChecker,
) -> None:
    """No warning for code outside integration modules."""
    code = f"""
{_IMPORTS}
device = DeviceInfo(
    connections={{(CONNECTION_NETWORK_MAC, format_mac(mac))}},
)
"""
    root_node = astroid.parse(code, "some_other.module")

    walker = ASTWalker(linter)
    walker.add_checker(format_mac_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
