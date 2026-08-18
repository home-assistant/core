"""Tests for the test-before-configure quality scale checker."""

import json
from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.quality_scale.test_before_configure import (
    TestBeforeConfigureChecker,
)
from pylint_home_assistant.helpers.integration import clear_caches
from pylint_home_assistant.helpers.quality_scale import clear_quality_scale_cache
import pytest
import yaml

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

_MODULE_NAME = "homeassistant.components.test_integration.config_flow"

_FLOW_WITHOUT_TEST = """
from homeassistant.config_entries import ConfigFlow

class MyConfigFlow(ConfigFlow, domain="test_integration"):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Test", data=user_input)
        return self.async_show_form(step_id="user")
"""


@pytest.fixture(name="configure_checker")
def configure_checker_fixture(linter: UnittestLinter) -> TestBeforeConfigureChecker:
    """Fixture to provide a test before configure checker."""
    clear_quality_scale_cache()
    clear_caches()
    return TestBeforeConfigureChecker(linter)


def _make_integration(
    tmp_path: Path, rules: dict | None = None, manifest: dict | None = None
) -> Path:
    """Create a fake integration directory."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_integration"
    integration_dir.mkdir(parents=True)
    if rules is not None:
        (integration_dir / "quality_scale.yaml").write_text(yaml.dump({"rules": rules}))
    (integration_dir / "manifest.json").write_text(
        json.dumps({"domain": "test_integration"} | (manifest or {}))
    )
    return integration_dir


def _parse_config_flow(
    integration_dir: Path, source: str, module_name: str = _MODULE_NAME
) -> astroid.Module:
    """Parse the integration's config_flow module."""
    root_node = astroid.parse(source, module_name)
    root_node.file = str(integration_dir / "config_flow.py")
    return root_node


def _expect_missing(class_node: nodes.ClassDef) -> MessageTest:
    """Build the expected MessageTest for a flagged config flow class."""
    pos = class_node.position
    return MessageTest(
        msg_id="home-assistant-missing-test-before-configure",
        node=class_node,
        line=pos.lineno,
        col_offset=pos.col_offset,
        end_line=pos.end_lineno,
        end_col_offset=pos.end_col_offset,
    )


@pytest.mark.parametrize(
    "flow_body",
    [
        pytest.param(
            """
    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await MyClient(user_input["host"]).get_data()
            except MyException:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Test", data=user_input)
        return self.async_show_form(step_id="user", errors=errors)
""",
            id="try_except_with_errors",
        ),
        pytest.param(
            """
    async def async_step_user(self, user_input=None):
        errors = None
        if user_input is not None:
            errors = await validate_input(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="Test", data=user_input)
        return self.async_show_form(step_id="user", errors=errors)
""",
            id="errors_from_helper_call",
        ),
        pytest.param(
            """
    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            if not await MyClient(user_input["host"]).connect():
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Test", data=user_input)
        return self.async_show_form(step_id="user", errors=errors)
""",
            id="errors_subscript_without_try",
        ),
        pytest.param(
            """
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            serial, errors = await self._validate_host(user_input["host"])
            if not errors:
                return self.async_create_entry(title="Test", data=user_input)
        return self.async_show_form(step_id="user", errors=errors)
""",
            id="errors_from_tuple_unpacking",
        ),
        pytest.param(
            """
    async def async_step_confirm(self, user_input=None):
        try:
            await self._probe_device()
        except TimeoutError:
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(title="Test", data={})
""",
            id="catch_and_abort",
        ),
        pytest.param(
            """
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            feed = await async_fetch_feed(self.hass, user_input["url"])
            if feed.bozo:
                return self.async_show_form(
                    step_id="user", errors={"base": "url_error"}
                )
            return self.async_create_entry(title="Test", data=user_input)
        return self.async_show_form(step_id="user")
""",
            id="errors_literal_kwarg",
        ),
    ],
)
def test_before_configure_evidence_present(
    linter: UnittestLinter,
    configure_checker: TestBeforeConfigureChecker,
    tmp_path: Path,
    flow_body: str,
) -> None:
    """No warning when the config flow surfaces failures to the user."""
    integration_dir = _make_integration(tmp_path, {"test-before-configure": "done"})
    root_node = _parse_config_flow(
        integration_dir,
        "from homeassistant.config_entries import ConfigFlow\n"
        f'class MyConfigFlow(ConfigFlow, domain="test_integration"):\n{flow_body}',
    )

    with assert_no_messages(linter):
        walk_checker(linter, configure_checker, root_node)


_FLOW_DETECTED_NOT_SURFACED = """
from homeassistant.config_entries import ConfigFlow

class MyConfigFlow(ConfigFlow, domain="test_integration"):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            serial, errors = await self._validate_host(user_input["host"])
            if not errors:
                return self.async_create_entry(title="Test", data=user_input)
        return self.async_show_form(step_id="user")
"""

_FLOW_SWALLOWED_EXCEPTION = """
from homeassistant.config_entries import ConfigFlow

class MyConfigFlow(ConfigFlow, domain="test_integration"):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            try:
                await MyClient(user_input["host"]).get_data()
            except MyException:
                pass
            return self.async_create_entry(title="Test", data=user_input)
        return self.async_show_form(step_id="user")
"""


@pytest.mark.parametrize(
    ("flow_source", "manifest"),
    [
        pytest.param(_FLOW_WITHOUT_TEST, None, id="no_evidence"),
        pytest.param(
            _FLOW_WITHOUT_TEST,
            {"bluetooth": [{"connectable": True}]},
            id="discovery_manifest_does_not_skip",
        ),
        pytest.param(_FLOW_DETECTED_NOT_SURFACED, None, id="detected_but_not_surfaced"),
        pytest.param(_FLOW_SWALLOWED_EXCEPTION, None, id="swallowed_exception"),
    ],
)
def test_before_configure_missing_fires(
    linter: UnittestLinter,
    configure_checker: TestBeforeConfigureChecker,
    tmp_path: Path,
    flow_source: str,
    manifest: dict | None,
) -> None:
    """Warning when the config flow never surfaces connection failures to the user."""
    integration_dir = _make_integration(
        tmp_path, {"test-before-configure": "done"}, manifest
    )
    root_node = _parse_config_flow(integration_dir, flow_source)
    class_node = root_node.body[-1]

    with assert_adds_messages(linter, _expect_missing(class_node)):
        walk_checker(linter, configure_checker, root_node)


def test_before_configure_oauth_flow_skipped(
    linter: UnittestLinter,
    configure_checker: TestBeforeConfigureChecker,
    tmp_path: Path,
) -> None:
    """No warning for OAuth flows; the token exchange is the connection test."""
    integration_dir = _make_integration(tmp_path, {"test-before-configure": "done"})
    root_node = _parse_config_flow(
        integration_dir,
        """
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

class MyConfigFlow(AbstractOAuth2FlowHandler, domain="test_integration"):
    async def async_oauth_create_entry(self, data):
        return self.async_create_entry(title="Test", data=data)
""",
    )

    with assert_no_messages(linter):
        walk_checker(linter, configure_checker, root_node)


def test_before_configure_inherited_evidence(
    linter: UnittestLinter,
    configure_checker: TestBeforeConfigureChecker,
    tmp_path: Path,
) -> None:
    """No warning when surfacing evidence lives in an inherited flow class's module."""
    astroid.parse(
        """
from homeassistant.config_entries import ConfigFlow

class BaseHardwareFlow(ConfigFlow):
    async def async_step_confirm(self, user_input=None):
        try:
            await self._probe_device()
        except TimeoutError:
            return self.async_abort(reason="cannot_connect")
        return self._async_flow_finished()
""",
        "homeassistant.components.hw_base.firmware_flow",
    )
    integration_dir = _make_integration(tmp_path, {"test-before-configure": "done"})
    root_node = _parse_config_flow(
        integration_dir,
        """
from homeassistant.components.hw_base.firmware_flow import BaseHardwareFlow

class MyConfigFlow(BaseHardwareFlow, domain="test_integration"):
    def _async_flow_finished(self):
        return self.async_create_entry(title="Test", data={})
""",
    )

    with assert_no_messages(linter):
        walk_checker(linter, configure_checker, root_node)


def test_before_configure_inherited_entry_creation_fires(
    linter: UnittestLinter,
    configure_checker: TestBeforeConfigureChecker,
    tmp_path: Path,
) -> None:
    """Warning when entry creation is inherited and nothing surfaces failures."""
    astroid.parse(
        """
from homeassistant.config_entries import ConfigFlow

class BaseSharedFlow(ConfigFlow):
    async def async_step_user(self, user_input=None):
        return self.async_create_entry(title="Test", data={})
""",
        "homeassistant.components.shared_base.config_flow",
    )
    integration_dir = _make_integration(tmp_path, {"test-before-configure": "done"})
    root_node = _parse_config_flow(
        integration_dir,
        """
from homeassistant.components.shared_base.config_flow import BaseSharedFlow

class MyConfigFlow(BaseSharedFlow, domain="test_integration"):
    VERSION = 1
""",
    )
    class_node = root_node.body[-1]

    with assert_adds_messages(linter, _expect_missing(class_node)):
        walk_checker(linter, configure_checker, root_node)


def test_before_configure_non_config_flow_class(
    linter: UnittestLinter,
    configure_checker: TestBeforeConfigureChecker,
    tmp_path: Path,
) -> None:
    """No warning for classes that are not config flows."""
    integration_dir = _make_integration(tmp_path, {"test-before-configure": "done"})
    root_node = _parse_config_flow(
        integration_dir,
        """
class MyHelper:
    def make(self):
        return self.async_create_entry(title="Test", data={})
""",
    )

    with assert_no_messages(linter):
        walk_checker(linter, configure_checker, root_node)


@pytest.mark.parametrize(
    ("module_name", "rules"),
    [
        pytest.param(
            _MODULE_NAME,
            None,
            id="no_quality_scale_file",
        ),
        pytest.param(
            _MODULE_NAME,
            {"test-before-configure": "todo"},
            id="rule_todo",
        ),
        pytest.param(
            _MODULE_NAME,
            {"test-before-configure": {"status": "exempt", "comment": "reason"}},
            id="rule_exempt",
        ),
        pytest.param(
            "homeassistant.components.test_integration.sensor",
            {"test-before-configure": "done"},
            id="not_config_flow_module",
        ),
        pytest.param(
            "not_homeassistant.something",
            {"test-before-configure": "done"},
            id="not_an_integration",
        ),
    ],
)
def test_before_configure_not_fired(
    linter: UnittestLinter,
    configure_checker: TestBeforeConfigureChecker,
    tmp_path: Path,
    module_name: str,
    rules: dict | None,
) -> None:
    """No warning when the rule is not done or the module is not config_flow."""
    integration_dir = _make_integration(tmp_path, rules)
    root_node = _parse_config_flow(integration_dir, _FLOW_WITHOUT_TEST, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, configure_checker, root_node)
