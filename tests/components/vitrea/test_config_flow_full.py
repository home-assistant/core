"""Vitrea config flow test coverage."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.vitrea.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {CONF_HOST: "127.0.0.1", CONF_PORT: 80}


@pytest.fixture(autouse=True)
def patch_vitrea_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch VitreaClient for all config flow tests."""
    monkeypatch.setattr(
        "homeassistant.components.vitrea.config_flow.VitreaConfigFlow._async_test_connection",
        lambda self, host, port: None,
    )


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""

    # Define a proper async function for patching
    async def async_test_connection(self, host, port):
        """Mock test connection that succeeds."""
        return

    with (
        patch(
            "homeassistant.components.vitrea.config_flow.VitreaConfigFlow._async_test_connection",
            new=async_test_connection,
        ),
        patch(
            "homeassistant.components.vitrea.async_setup_entry",
            return_value=True,
        ),
    ):
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
        assert (
            result2["title"]
            == f"Vitrea {TEST_USER_INPUT[CONF_HOST]}:{TEST_USER_INPUT[CONF_PORT]}"
        )
        assert result2["data"] == TEST_USER_INPUT


@pytest.mark.asyncio
async def test_user_flow_connection_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test connection error in user config flow."""
    monkeypatch.setattr(
        "homeassistant.components.vitrea.config_flow.VitreaConfigFlow._async_test_connection",
        lambda self, host, port: (_ for _ in ()).throw(ConnectionError("fail")),
    )
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


@pytest.mark.asyncio
async def test_user_flow_duplicate_entry(hass: HomeAssistant) -> None:
    """Test duplicate prevention in config flow."""
    # First, set up a mock entry to be detected as a duplicate
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id=f"vitrea_{TEST_USER_INPUT[CONF_HOST]}_{TEST_USER_INPUT[CONF_PORT]}",
    )
    entry.add_to_hass(hass)

    # Now start the config flow
    async def async_test_connection(self, host, port):
        """Mock test connection that succeeds."""
        return

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaConfigFlow._async_test_connection",
        new=async_test_connection,
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
