"""Test the Ouman EH-800 config flow."""

from unittest.mock import AsyncMock

from ouman_eh_800_api import (
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
)
import pytest

from homeassistant.components.ouman_eh_800.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_PASSWORD, TEST_URL, TEST_USERNAME

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {
    CONF_URL: TEST_URL,
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
}


@pytest.mark.usefixtures("mock_ouman_client")
@pytest.mark.parametrize(
    ("submitted_url", "expected_url"),
    [
        pytest.param(TEST_URL, TEST_URL, id="already_normalized"),
        pytest.param(f"{TEST_URL}/eh800.html", TEST_URL, id="html_path"),
        pytest.param(f"{TEST_URL}:80/eh800.html/", TEST_URL, id="port_80_and_path"),
        pytest.param(
            f"{TEST_URL}:8080/eh800.html",
            f"{TEST_URL}:8080",
            id="non_default_port",
        ),
        pytest.param(
            "https://proxied.device.com/eh800.html/",
            "https://proxied.device.com",
            id="https_url",
        ),
    ],
)
async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    submitted_url: str,
    expected_url: str,
) -> None:
    """Test the user flow accepts and normalizes various URL forms."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: submitted_url,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ouman EH-800"
    assert result["data"] == {**USER_INPUT, CONF_URL: expected_url}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (OumanClientCommunicationError("Connection failed"), "cannot_connect"),
        (OumanClientAuthenticationError("Invalid credentials"), "invalid_auth"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
)
async def test_user_flow_errors_recover(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    error: Exception,
    expected_error: str,
) -> None:
    """Test that errors are surfaced and the flow can recover."""
    mock_ouman_client.login.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_ouman_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_ouman_client")
async def test_user_flow_invalid_url_recovers(hass: HomeAssistant) -> None:
    """Test that an unparsable URL surfaces an error and the flow can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "not a url",
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_ouman_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
