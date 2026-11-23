"""Test the Model Context Protocol Server diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .conftest import TEST_LLM_API_ID, MockLLMAPI


class _StubTool(llm.Tool):
    """Stub tool with configurable annotations."""

    def __init__(self, name: str, read_only: bool) -> None:
        """Initialize the tool."""
        self.name = name
        self.annotations = llm.ToolAnnotations(read_only=read_only)

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict:
        """Return an empty result."""
        return {}


@pytest.mark.usefixtures("hass_owner_user")
@pytest.mark.parametrize("llm_hass_api", [[TEST_LLM_API_ID]])
@pytest.mark.parametrize(
    "read_only",
    [pytest.param(False, id="all_tools"), pytest.param(True, id="read_only")],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    llm.async_register_api(
        hass,
        MockLLMAPI(
            hass=hass,
            id=TEST_LLM_API_ID,
            name="Test API",
            requires_admin=True,
            tools=[
                _StubTool("read_tool", read_only=True),
                _StubTool("write_tool", read_only=False),
            ],
        ),
    )
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )


@pytest.mark.parametrize("llm_hass_api", [["missing-api"]])
async def test_diagnostics_missing_llm_api(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when a configured LLM API no longer exists."""
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )


@pytest.mark.parametrize("llm_hass_api", [[TEST_LLM_API_ID, "other-api"]])
async def test_diagnostics_tool_name_collision(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when merging the LLM APIs fails on a tool name collision."""
    llm.async_register_api(
        hass,
        MockLLMAPI(
            hass=hass,
            id=TEST_LLM_API_ID,
            name="Test API",
            tools=[
                _StubTool("duplicate", read_only=True),
                _StubTool("duplicate", read_only=True),
            ],
        ),
    )
    llm.async_register_api(
        hass,
        MockLLMAPI(
            hass=hass,
            id="other-api",
            name="Other API",
            tools=[_StubTool("duplicate", read_only=True)],
        ),
    )
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
