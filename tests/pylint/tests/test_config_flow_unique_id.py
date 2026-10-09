"""Tests for the config flow unique ID checker."""

from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.tests.config_flow_unique_id import (
    ConfigFlowUniqueId,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

_MODULE_NAME = "tests.components.test_integration.test_config_flow"

_CONFIG_FLOW = """
class MyConfigFlow(ConfigFlow, domain="test_integration"):
    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("1234")
        return self.async_create_entry(title="Test", data={})
"""

_HAPPY_FLOW = """
async def test_full_flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.1.1.1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
"""


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> ConfigFlowUniqueId:
    """Fixture to provide a config flow unique ID checker."""
    return ConfigFlowUniqueId(linter)


def _parse_test_module(
    tmp_path: Path,
    source: str,
    *,
    module_name: str = _MODULE_NAME,
    config_flow_files: dict[str, str] | None = None,
) -> nodes.Module:
    """Create a fake integration and parse a test module for it."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_integration"
    for name, content in (
        config_flow_files or {"config_flow.py": _CONFIG_FLOW}
    ).items():
        (integration_dir / name).parent.mkdir(parents=True, exist_ok=True)
        (integration_dir / name).write_text(content)
    root_node = astroid.parse(source, module_name)
    root_node.file = str(
        tmp_path / "tests" / "components" / "test_integration" / "test_config_flow.py"
    )
    return root_node


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def test_full_flow(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "1234"
""",
            id="result_unique_id",
        ),
        pytest.param(
            """
async def test_full_flow(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "1234"
""",
            id="entry_unique_id",
        ),
        pytest.param(
            """
async def test_full_flow(hass, snapshot):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result == snapshot
""",
            id="snapshot",
        ),
        pytest.param(
            """
async def test_flow_recovers(hass, mock_client):
    mock_client.connect.side_effect = ConnectionError
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="recovers_from_side_effect",
        ),
        pytest.param(
            """
async def test_flow_recovers(hass):
    with patch("homeassistant.components.test_integration.connect", side_effect=OSError):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="recovers_from_patched_side_effect",
        ),
        pytest.param(
            """
async def test_flow_recovers(hass, mock_client, exception):
    mock_client.connect.side_effect = exception
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    mock_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="recovers_from_parametrized_side_effect",
        ),
        pytest.param(
            """
async def test_flow_recovers(hass, mock_client):
    mock_client.connect.side_effect = [ConnectionError("offline"), None]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="recovers_from_side_effect_list",
        ),
        pytest.param(
            """
async def test_flow_recovers(hass, mock_client):
    mock_client.connect.side_effect = LibraryConnectionError
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="recovers_from_unresolved_error",
        ),
        pytest.param(
            """
async def test_flow_recovers(hass, error):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": error}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="recovers_from_expected_errors",
        ),
        pytest.param(
            """
async def test_flow_recovers(hass, expected_errors):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == expected_errors
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="recovers_from_parametrized_errors",
        ),
        pytest.param(
            """
async def test_options_flow(hass, config_entry):
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="options_flow",
        ),
        pytest.param(
            """
async def test_options_flow(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
""",
            id="config_flow_as_options_flow_setup",
        ),
        pytest.param(
            """
async def test_subentry_flow(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.subentries.async_init(
        (result["result"].entry_id, "device"), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
""",
            id="config_flow_as_subentry_flow_setup",
        ),
        pytest.param(
            """
async def test_subentry_flow(hass, config_entry):
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="subentry_flow",
        ),
        pytest.param(
            """
async def test_already_configured(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
""",
            id="abort",
        ),
        pytest.param(
            """
async def _finish_flow(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="not_a_test_function",
        ),
    ],
)
def test_no_message(
    linter: UnittestLinter,
    checker: ConfigFlowUniqueId,
    tmp_path: Path,
    code: str,
) -> None:
    """Test tests that check the unique ID or don't need to."""
    with assert_no_messages(linter):
        walk_checker(linter, checker, _parse_test_module(tmp_path, code))


@pytest.mark.parametrize(
    "module_name",
    [
        pytest.param("tests.components.test_integration.test_init", id="test_init"),
        pytest.param(
            "tests.components.test_integration.test_config_flow_helpers",
            id="other_config_flow_module",
        ),
        pytest.param(
            "homeassistant.components.test_integration.test_config_flow",
            id="not_a_test_module",
        ),
        pytest.param("tests.helpers.test_config_flow", id="not_an_integration"),
    ],
)
def test_module_not_checked(
    linter: UnittestLinter,
    checker: ConfigFlowUniqueId,
    tmp_path: Path,
    module_name: str,
) -> None:
    """Test only integration test_config_flow modules are checked."""
    root_node = _parse_test_module(tmp_path, _HAPPY_FLOW, module_name=module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "config_flow_files",
    [
        pytest.param(
            {
                "config_flow.py": (
                    'class MyConfigFlow(ConfigFlow, domain="test_integration"):\n'
                    "    pass\n"
                )
            },
            id="no_unique_id",
        ),
        pytest.param({"manifest.json": "{}"}, id="no_config_flow"),
    ],
)
def test_flow_without_unique_id(
    linter: UnittestLinter,
    checker: ConfigFlowUniqueId,
    tmp_path: Path,
    config_flow_files: dict[str, str],
) -> None:
    """Test tests are not checked when the config flow sets no unique ID."""
    root_node = _parse_test_module(
        tmp_path, _HAPPY_FLOW, config_flow_files=config_flow_files
    )

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(_HAPPY_FLOW, id="happy_flow"),
        pytest.param(
            """
async def test_full_flow(hass):
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] == FlowResultType.CREATE_ENTRY
""",
            id="equality",
        ),
        pytest.param(
            """
async def test_full_flow(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("type") is FlowResultType.CREATE_ENTRY
""",
            id="get",
        ),
        pytest.param(
            """
async def test_full_flow(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == None
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="no_errors_literal",
        ),
        pytest.param(
            """
async def test_replaces_ignored(hass):
    MockConfigEntry(domain=DOMAIN, unique_id="1234", source=SOURCE_IGNORE)
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="unique_id_keyword_only",
        ),
        pytest.param(
            """
async def test_two_entries(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="flagged_once",
        ),
        pytest.param(
            """
async def test_full_flow(hass):
    result = await start_flow(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="result_from_helper",
        ),
        pytest.param(
            """
async def test_full_flow(hass, mock_client):
    mock_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="side_effect_reset",
        ),
        pytest.param(
            """
async def test_full_flow(hass):
    with patch("homeassistant.components.test_integration.connect", side_effect=lambda: True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="side_effect_lambda",
        ),
        pytest.param(
            """
async def test_full_flow(hass):
    async def mock_connect():
        return True

    with patch("homeassistant.components.test_integration.connect", side_effect=mock_connect):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="side_effect_function",
        ),
        pytest.param(
            """
async def test_full_flow(hass):
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"unique_id": "1234"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            id="unique_id_not_asserted",
        ),
    ],
)
@pytest.mark.parametrize(
    "config_flow_files",
    [
        pytest.param({"config_flow.py": _CONFIG_FLOW}, id="module"),
        pytest.param(
            {"config_flow/__init__.py": "", "config_flow/user.py": _CONFIG_FLOW},
            id="package",
        ),
    ],
)
def test_missing_unique_id(
    linter: UnittestLinter,
    checker: ConfigFlowUniqueId,
    tmp_path: Path,
    code: str,
    config_flow_files: dict[str, str],
) -> None:
    """Test happy path tests that skip the unique ID are flagged once."""
    root_node = _parse_test_module(tmp_path, code, config_flow_files=config_flow_files)
    compare = next(
        node
        for node in root_node.nodes_of_class(nodes.Compare)
        if "CREATE_ENTRY" in node.as_string()
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-tests-config-flow-unique-id",
            node=compare,
            line=compare.lineno,
            col_offset=compare.col_offset,
            end_line=compare.end_lineno,
            end_col_offset=compare.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root_node)
