"""Unit-tests for Swidget config_flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.swidget import DOMAIN, config_flow
from homeassistant.components.swidget.config_flow import CannotConnect
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_HOST = "1.1.1.1"
TEST_PASSWORD = "0123456789abcdef0123456789abcdef"


@pytest.fixture(name="client_connect", autouse=True)
def client_connect_fixture() -> Generator[AsyncMock, None, None]:
    """Mock server version."""
    with patch(
        "homeassistant.components.swidget.config_flow.SwidgetDevice"
    ) as client_connect:
        yield client_connect


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]


async def test_user_flow(hass):
    """Test the user flow."""
    flow = config_flow.SwidgetConfigFlow()

    # Test step user
    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["data_schema"] == config_flow.STEP_USER_DATA_SCHEMA


async def test_success(hass: HomeAssistant) -> None:
    """Test for a successful setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.swidget.config_flow.validate_input",
            return_value={"title": "Test Device", "unique_id": "test_device_12345678"},
        ),
        patch(
            "homeassistant.components.swidget.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Device"
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test for a failed setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    with (
        patch(
            "homeassistant.components.swidget.config_flow.validate_input",
            return_value=CannotConnect,
        ),
        patch(
            "homeassistant.components.swidget.async_setup_entry",
            return_value=False,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
    assert len(mock_setup_entry.mock_calls) == 0
