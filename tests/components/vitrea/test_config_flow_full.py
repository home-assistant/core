"""Vitrea config flow test coverage."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.vitrea.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {CONF_HOST: "127.0.0.1", CONF_PORT: 80}


@pytest.fixture(autouse=True)
def patch_vitrea_client():
    """Patch VitreaClient."""
    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient", autospec=True
    ) as client_mock:
        client_mock.return_value.status_request = AsyncMock(return_value=None)
        yield client_mock


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""

    # Define a proper async function for patching
    async def async_test_connection(self, host, port):
        """Mock test connection that succeeds."""
        return

    with patch("homeassistant.components.vitrea.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )
        await hass.async_block_till_done()

        # Check for errors in debug mode if needed
        if result2["type"] == FlowResultType.FORM:
            # Log errors without using print
            pytest.fail(
                f"Unexpected form result with errors: {result2.get('errors', {})}"
            )

        assert result2["type"] == FlowResultType.CREATE_ENTRY, (
            f"Unexpected result: {result2}"
        )
        assert result2["title"] == f"Vitrea ({TEST_USER_INPUT[CONF_HOST]})"
        assert result2["data"] == TEST_USER_INPUT


async def test_user_flow_connection_error(hass: HomeAssistant) -> None:
    """Test connection error in user config flow."""
    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient"
    ) as client_mock:
        client_mock.return_value.connect.side_effect = ConnectionError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_entry(hass: HomeAssistant) -> None:
    """Test duplicate prevention in config flow."""
    # First, set up a mock entry to be detected as a duplicate
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id=TEST_USER_INPUT[CONF_HOST],  # Use host as unique_id
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient.connect",
        new=lambda self, host, port: None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Try to configure with the same data that matches the existing entry
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )

        # This should abort with "already_configured"
        assert result2["type"] == "abort", f"Expected abort but got {result2['type']}"
        assert result2["reason"] == "already_configured"
