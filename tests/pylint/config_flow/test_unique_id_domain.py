"""Tests for the config flow unique ID domain checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.config_flow.unique_id_domain import (
    ConfigFlowUniqueIdDomainChecker,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

_MODULE = "homeassistant.components.test_int.config_flow"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> ConfigFlowUniqueIdDomainChecker:
    """Fixture to provide a config flow unique ID domain checker."""
    return ConfigFlowUniqueIdDomainChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            "await self.async_set_unique_id(device.serial_number)",
            _MODULE,
            id="device_id",
        ),
        pytest.param(
            'await self.async_set_unique_id(f"{DOMAIN}_{device.serial_number}")',
            _MODULE,
            id="domain_prefix",
        ),
        pytest.param(
            'await self.async_set_unique_id("other_domain")',
            _MODULE,
            id="other_string",
        ),
        pytest.param(
            "await self.async_set_unique_id(None)",
            _MODULE,
            id="none",
        ),
        pytest.param(
            "await self.async_set_unique_id(DOMAIN)",
            "homeassistant.helpers.my_helper",
            id="not_an_integration",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: ConfigFlowUniqueIdDomainChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("await self.async_set_unique_id(DOMAIN)", id="domain_constant"),
        pytest.param(
            "await self.async_set_unique_id(const.DOMAIN)", id="domain_attribute"
        ),
        pytest.param('await self.async_set_unique_id("test_int")', id="domain_string"),
        pytest.param(
            "await self.async_set_unique_id(unique_id=DOMAIN)", id="keyword_argument"
        ),
        pytest.param(
            "entry = await self.async_set_unique_id(DOMAIN, raise_on_progress=False)",
            id="raise_on_progress",
        ),
    ],
)
def test_unique_id_domain(
    linter: UnittestLinter,
    checker: ConfigFlowUniqueIdDomainChecker,
    code: str,
) -> None:
    """Test using the domain as unique ID is flagged."""
    root = astroid.parse(code, _MODULE)
    call = next(root.nodes_of_class(nodes.Call))

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-config-flow-unique-id-domain",
            node=call,
            line=call.lineno,
            col_offset=call.col_offset,
            end_line=call.end_lineno,
            end_col_offset=call.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root)
