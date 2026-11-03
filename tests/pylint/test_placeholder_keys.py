"""Tests for the placeholder keys checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.placeholder_keys import PlaceholderKeysChecker
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker


@pytest.fixture(name="placeholder_keys_checker")
def placeholder_keys_checker_fixture(
    linter: UnittestLinter,
) -> PlaceholderKeysChecker:
    """Fixture to provide a placeholder keys checker."""
    return PlaceholderKeysChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
self.async_show_form(description_placeholders={"username": username})
""",
            id="string_literal",
        ),
        pytest.param(
            """
self.async_show_form(description_placeholders={"username": data[CONF_USERNAME]})
""",
            id="constant_in_value",
        ),
        pytest.param(
            """
self.async_show_form(description_placeholders={PLACEHOLDER_URL: url})
""",
            id="placeholder_prefix",
        ),
        pytest.param(
            """
self.async_show_form(description_placeholders={MyPlaceholder.URL: url})
""",
            id="placeholder_enum",
        ),
        pytest.param(
            """
self.async_show_form(description_placeholders={**PLACEHOLDERS, "name": name})
""",
            id="dict_unpack",
        ),
        pytest.param(
            """
self.async_show_form(description_placeholders=PLACEHOLDERS)
""",
            id="not_a_dict",
        ),
        pytest.param(
            """
async_create_issue(translation_placeholders={retired.placeholder: names})
""",
            id="dynamic_attribute",
        ),
        pytest.param(
            """
async_create_issue(translation_placeholders={key: value})
""",
            id="dynamic_name",
        ),
        pytest.param(
            """
async_create_issue(hass, DOMAIN, "issue", data={CONF_HOST: host})
""",
            id="other_keyword",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    placeholder_keys_checker: PlaceholderKeysChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_int.config_flow")
    with assert_no_messages(linter):
        walk_checker(linter, placeholder_keys_checker, root_node)


@pytest.mark.parametrize(
    ("code", "key"),
    [
        pytest.param(
            """
self.async_show_form(description_placeholders={CONF_USERNAME: username})
""",
            "CONF_USERNAME",
            id="description_placeholders_conf",
        ),
        pytest.param(
            """
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="error",
    translation_placeholders={CONF_HOST: host},
)
""",
            "CONF_HOST",
            id="translation_placeholders_conf",
        ),
        pytest.param(
            """
self.async_show_form(description_placeholders={const.CONF_NAME: name})
""",
            "const.CONF_NAME",
            id="module_attribute",
        ),
        pytest.param(
            """
self.async_show_form(description_placeholders={AUTH_HELP_URL_KEY: url})
""",
            "AUTH_HELP_URL_KEY",
            id="other_constant",
        ),
        pytest.param(
            """
self.async_show_form(description_placeholders={ConfigKeys.USERNAME: username})
""",
            "ConfigKeys.USERNAME",
            id="other_enum",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    placeholder_keys_checker: PlaceholderKeysChecker,
    code: str,
    key: str,
) -> None:
    """Test cases that should trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_int.config_flow")
    key_node = next(root_node.nodes_of_class(nodes.Dict)).items[0][0]
    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-placeholder-key",
            node=key_node,
            args=(key,),
            line=key_node.lineno,
            col_offset=key_node.col_offset,
            end_line=key_node.end_lineno,
            end_col_offset=key_node.end_col_offset,
        ),
    ):
        walk_checker(linter, placeholder_keys_checker, root_node)
