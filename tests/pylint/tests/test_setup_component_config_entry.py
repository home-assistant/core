"""Tests for the setup component config entry checker."""

import json
from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.tests.setup_component_config_entry import (
    SetupComponentConfigEntry,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

_MODULE_NAME = "tests.components.test_integration.test_init"

_SETUP_ENTRY_ONLY = """
async def async_setup_entry(hass, entry):
    return True
"""

_ENTRY_ONLY_SCHEMA = """
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass, config):
    async_setup_services(hass)
    return True
"""

_YAML_SCHEMA = """
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    return True
"""

_SETUP_WITH_DOMAIN = """
DOMAIN = "test_integration"

async def test_setup(hass):
    assert await async_setup_component(hass, DOMAIN, {})
"""


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> SetupComponentConfigEntry:
    """Fixture to provide a setup component config entry checker."""
    return SetupComponentConfigEntry(linter)


def _parse_test_module(
    tmp_path: Path,
    source: str,
    *,
    module_name: str = _MODULE_NAME,
    init: str = _SETUP_ENTRY_ONLY,
    config_flow: bool = True,
) -> nodes.Module:
    """Create a fake integration and parse a test module for it."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_integration"
    integration_dir.mkdir(parents=True)
    (integration_dir / "__init__.py").write_text(init)
    (integration_dir / "manifest.json").write_text(
        json.dumps({"domain": "test_integration", "config_flow": config_flow})
    )
    root_node = astroid.parse(source, module_name)
    root_node.file = str(
        tmp_path / "tests" / "components" / "test_integration" / "test_init.py"
    )
    return root_node


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            _SETUP_WITH_DOMAIN,
            id="domain_constant",
        ),
        pytest.param(
            """
async def test_setup(hass):
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
""",
            id="uninferred_domain_constant",
        ),
        pytest.param(
            """
async def test_setup(hass):
    assert await async_setup_component(hass, "test_integration", {})
""",
            id="domain_string",
        ),
        pytest.param(
            """
from homeassistant import setup

async def test_setup(hass):
    await setup.async_setup_component(hass, const.DOMAIN, {})
""",
            id="attribute_calls",
        ),
        pytest.param(
            """
async def test_setup(hass):
    await async_setup_component(hass=hass, domain="test_integration", config={})
""",
            id="keyword_arguments",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: SetupComponentConfigEntry,
    tmp_path: Path,
    code: str,
) -> None:
    """Test setting up the tested integration as a component is flagged."""
    root_node = _parse_test_module(tmp_path, code)
    call = next(
        call
        for call in root_node.nodes_of_class(nodes.Call)
        if call.func.as_string().endswith("async_setup_component")
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-tests-setup-component-config-entry",
            node=call,
            args=("test_integration",),
            line=call.lineno,
            col_offset=call.col_offset,
            end_line=call.end_lineno,
            end_col_offset=call.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root_node)


def test_entry_only_config_schema(
    linter: UnittestLinter,
    checker: SetupComponentConfigEntry,
    tmp_path: Path,
) -> None:
    """Test an integration with an entry only config schema is checked."""
    root_node = _parse_test_module(
        tmp_path, _SETUP_WITH_DOMAIN, init=_ENTRY_ONLY_SCHEMA
    )
    walk_checker(linter, checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-tests-setup-component-config-entry"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def test_setup(hass, entry):
    await hass.config_entries.async_setup(entry.entry_id)
""",
            id="config_entry_setup",
        ),
        pytest.param(
            """
async def test_setup(hass):
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, SENSOR_DOMAIN, {})
""",
            id="other_domain",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import DOMAIN

async def test_setup(hass):
    assert await async_setup_component(hass, DOMAIN, {})
""",
            id="imported_domain_of_other_integration",
        ),
        pytest.param(
            """
async def test_setup(hass):
    assert await async_setup_component(hass)
""",
            id="no_domain_argument",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: SetupComponentConfigEntry,
    tmp_path: Path,
    code: str,
) -> None:
    """Test calls that don't set up the tested integration are not flagged."""
    root_node = _parse_test_module(tmp_path, code)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("init", "config_flow"),
    [
        pytest.param(_YAML_SCHEMA, True, id="accepts_yaml"),
        pytest.param(_SETUP_ENTRY_ONLY, False, id="no_config_flow"),
    ],
)
def test_integration_not_checked(
    linter: UnittestLinter,
    checker: SetupComponentConfigEntry,
    tmp_path: Path,
    init: str,
    config_flow: bool,
) -> None:
    """Test integrations without a config flow or with YAML are not checked."""
    root_node = _parse_test_module(
        tmp_path, _SETUP_WITH_DOMAIN, init=init, config_flow=config_flow
    )

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


def test_not_a_test_module(
    linter: UnittestLinter,
    checker: SetupComponentConfigEntry,
    tmp_path: Path,
) -> None:
    """Test modules outside of the tests are not checked."""
    root_node = _parse_test_module(
        tmp_path,
        _SETUP_WITH_DOMAIN,
        module_name="homeassistant.components.test_integration.helpers",
    )

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)
