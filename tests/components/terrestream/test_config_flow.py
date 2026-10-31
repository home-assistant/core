"""Test physical pairing and duplicate prevention."""

from dataclasses import asdict
from unittest.mock import ANY, AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from terrestream_local.errors import AuthenticationError, ClientError

from homeassistant.components.terrestream.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CREDENTIALS, HOST, UUID

pytestmark = pytest.mark.usefixtures("mock_client", "mock_setup_entry")


async def test_pairing(hass: HomeAssistant, mock_pair_device: AsyncMock) -> None:
    """Show the form and persist pairing data, including leading code zeros."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    mock_pair_device.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": HOST, "code": "00123456"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UUID
    assert result["data"] == {"host": HOST, "credentials": asdict(CREDENTIALS)}
    mock_pair_device.assert_awaited_once_with(ANY, HOST, "00123456")


@pytest.mark.parametrize(
    ("error", "expected", "host"),
    [
        pytest.param(
            AuthenticationError("invalid"), "invalid_auth", HOST, id="wrong-code"
        ),
        pytest.param(ClientError("offline"), "cannot_connect", HOST, id="offline"),
        pytest.param(
            ValueError("host"),
            "cannot_connect",
            "https://192.0.2.10",
            id="invalid-address",
        ),
    ],
)
async def test_pairing_error(
    hass: HomeAssistant,
    mock_pair_device: AsyncMock,
    error: Exception,
    expected: str,
    host: str,
) -> None:
    """Recover from a pairing failure within the same config flow."""
    mock_pair_device.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": host, "code": "00123456"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    mock_pair_device.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": HOST, "code": "00123456"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UUID
    assert result["data"] == {"host": HOST, "credentials": asdict(CREDENTIALS)}


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("1234567", id="too-short"),
        pytest.param("123456789", id="too-long"),
        pytest.param("1234abcd", id="letters"),
        pytest.param("１２３４５６７８", id="non-ascii-digits"),
        pytest.param("1234567 ", id="whitespace"),
        pytest.param("", id="empty"),
    ],
)
async def test_malformed_pairing_code(
    hass: HomeAssistant, mock_pair_device: AsyncMock, code: str
) -> None:
    """Reject malformed codes before calling the library and allow correction."""
    mock_pair_device.side_effect = ValueError("Malformed pairing code")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": HOST, "code": code}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    mock_pair_device.assert_not_awaited()

    mock_pair_device.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": HOST, "code": "00123456"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UUID
    assert result["data"] == {"host": HOST, "credentials": asdict(CREDENTIALS)}
    mock_pair_device.assert_awaited_once_with(ANY, HOST, "00123456")


async def test_duplicate(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Keep the existing entry when the same device is paired again."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": HOST, "code": "00123456"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [config_entry]
