"""Common fixtures for the Model Context Protocol Server tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.mcp_server.const import CONF_REQUIRE_ADMIN, DOMAIN
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_LLM_API_ID = "test-api"


class MockLLMAPI(llm.API):
    """Test LLM API that does not expose any tools."""

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return a test API instance."""
        return llm.APIInstance(
            api=self,
            api_prompt="Test prompt",
            llm_context=llm_context,
            tools=[],
        )


@pytest.fixture(autouse=True)
async def ensure_homeassistant_loaded(hass: HomeAssistant) -> None:
    """Ensure homeassistant component is loaded."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mcp_server.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="llm_hass_api")
def llm_hass_api_fixture() -> list[str]:
    """Fixture for the config entry llm_hass_api."""
    return [llm.LLM_API_ASSIST]


@pytest.fixture(name="require_admin")
def require_admin_fixture() -> bool:
    """Fixture for the config entry require admin option."""
    return False


@pytest.fixture(name="config_entry")
def mock_config_entry(
    hass: HomeAssistant, llm_hass_api: str | list[str], require_admin: bool
) -> MockConfigEntry:
    """Fixture to load the integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LLM_HASS_API: llm_hass_api,
            CONF_REQUIRE_ADMIN: require_admin,
        },
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    return config_entry
