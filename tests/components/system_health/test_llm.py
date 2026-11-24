"""Tests for the system_health LLM tools."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockModule, MockUser, mock_integration

from homeassistant.components.system_health import DOMAIN
from homeassistant.components.system_health.llm import async_get_tools
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

TOOL_NAME = "system_health__get_system_info"

BASE_SYSTEM_INFO = {
    "arch": "x86_64",
    "dev": False,
    "docker": True,
    "installation_type": "Home Assistant Container",
    "os_name": "Linux",
    "os_version": "6.12.0",
    "python_version": "3.14.2",
    "timezone": "Europe/Amsterdam",
    "user": "root",
    "version": "2026.11.0",
    "virtualenv": False,
}
BASE_RESULT = {
    "installation_type": "Home Assistant Container",
    "core_version": "2026.11.0",
    "frontend_version": "20261101.0",
    "python_version": "3.14.2",
    "os_name": "Linux",
    "os_version": "6.12.0",
    "arch": "x86_64",
    "timezone": "Europe/Amsterdam",
}


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return an LLM context."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="en",
        assistant="conversation",
        device_id=None,
    )


async def test_async_get_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test async_get_tools returns tools only for Home Assistant API."""
    assert async_get_tools(hass, llm_context, llm.LLM_API_ASSIST) is None

    ha_tools = async_get_tools(hass, llm_context, llm.LLM_API_HOME_ASSISTANT)
    assert ha_tools is not None
    assert [tool.name for tool in ha_tools.tools] == [TOOL_NAME]
    assert ha_tools.prompt is None


@pytest.mark.parametrize(
    ("system_info", "expected_result"),
    [
        pytest.param(BASE_SYSTEM_INFO, BASE_RESULT, id="container"),
        pytest.param(
            {
                **BASE_SYSTEM_INFO,
                "installation_type": "Home Assistant OS",
                "hassio": True,
                "supervisor": "2026.10.2",
                "host_os": "Home Assistant OS 17.0",
                "docker_version": "28.3.3",
                "chassis": "embedded",
            },
            {
                **BASE_RESULT,
                "installation_type": "Home Assistant OS",
                "supervisor_version": "2026.10.2",
                "host_os": "Home Assistant OS 17.0",
            },
            id="supervisor",
        ),
    ],
)
async def test_get_system_info(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    llm_context: llm.LLMContext,
    system_info: dict[str, Any],
    expected_result: dict[str, Any],
) -> None:
    """Test the system info tool through the Home Assistant API."""
    mock_integration(
        hass,
        MockModule("frontend", requirements=["home-assistant-frontend==20261101.0"]),
    )
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)

    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    tool = next(tool for tool in api.tools if tool.name == TOOL_NAME)
    assert tool.integration == DOMAIN
    assert tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )

    with patch(
        "homeassistant.components.system_health.llm.async_get_system_info",
        return_value=system_info,
    ):
        result = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {}))

    assert result == llm.ToolResult(data={"result": expected_result})
