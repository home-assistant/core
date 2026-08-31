"""Test the Harbor config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.harbor.const import (
    CONF_CERT_PEM,
    CONF_KEY_PEM,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CERT_PEM, KEY_PEM, SERIAL, set_connected

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_mqtt_client")
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test the full user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERIAL: SERIAL,
            CONF_CERT_PEM: CERT_PEM,
            CONF_KEY_PEM: KEY_PEM,
            CONF_IP_ADDRESS: "192.168.1.10",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Camera {SERIAL}"
    assert result["result"].unique_id == SERIAL
    assert result["data"] == {
        CONF_SERIAL: SERIAL,
        CONF_CERT_PEM: CERT_PEM,
        CONF_KEY_PEM: KEY_PEM,
        CONF_IP_ADDRESS: "192.168.1.10",
    }
    client_id = mock_mqtt_client.call_args.kwargs["client_id"]
    assert client_id.startswith(f"{DOMAIN}-{SERIAL}-probe-")
    assert client_id != f"{DOMAIN}-{SERIAL}-probe"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_uses_friendly_name(
    hass: HomeAssistant, mock_mqtt_client: AsyncMock
) -> None:
    """Test the entry is titled with the camera's friendly name when set."""
    mock_mqtt_client.return_value.get_settings.return_value = SimpleNamespace(
        settings=SimpleNamespace(preference_display_name="Nursery")
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERIAL: SERIAL,
            CONF_CERT_PEM: CERT_PEM,
            CONF_KEY_PEM: KEY_PEM,
            CONF_IP_ADDRESS: "192.168.1.10",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nursery"


@pytest.mark.parametrize(
    ("user_input", "error_field", "error"),
    [
        (
            {
                CONF_SERIAL: "123",
                CONF_CERT_PEM: CERT_PEM,
                CONF_KEY_PEM: KEY_PEM,
                CONF_IP_ADDRESS: "192.168.1.10",
            },
            CONF_SERIAL,
            "invalid_serial",
        ),
        (
            {
                CONF_SERIAL: "abcdefghij",
                CONF_CERT_PEM: CERT_PEM,
                CONF_KEY_PEM: KEY_PEM,
                CONF_IP_ADDRESS: "192.168.1.10",
            },
            CONF_SERIAL,
            "invalid_serial",
        ),
        (
            {
                CONF_SERIAL: SERIAL,
                CONF_CERT_PEM: "not a cert",
                CONF_KEY_PEM: KEY_PEM,
                CONF_IP_ADDRESS: "192.168.1.10",
            },
            CONF_CERT_PEM,
            "invalid_cert",
        ),
        (
            {
                CONF_SERIAL: SERIAL,
                CONF_CERT_PEM: CERT_PEM,
                CONF_KEY_PEM: "not a key",
                CONF_IP_ADDRESS: "192.168.1.10",
            },
            CONF_KEY_PEM,
            "invalid_key",
        ),
    ],
    ids=["short_serial", "non_digit_serial", "bad_cert", "bad_key"],
)
@pytest.mark.usefixtures("mock_mqtt_client", "mock_setup_entry")
async def test_user_flow_validation_errors(
    hass: HomeAssistant,
    user_input: dict[str, str],
    error_field: str,
    error: str,
) -> None:
    """Test validation errors are surfaced and recoverable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {error_field: error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERIAL: SERIAL,
            CONF_CERT_PEM: CERT_PEM,
            CONF_KEY_PEM: KEY_PEM,
            CONF_IP_ADDRESS: "192.168.1.10",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the flow aborts when the serial is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERIAL: SERIAL,
            CONF_CERT_PEM: CERT_PEM,
            CONF_KEY_PEM: KEY_PEM,
            CONF_IP_ADDRESS: "192.168.1.10",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test the flow shows an error and recovers when the camera is unreachable."""
    # Start the probe client without ever reporting a successful connection.
    mock_mqtt_client.return_value.start.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERIAL: SERIAL,
            CONF_CERT_PEM: CERT_PEM,
            CONF_KEY_PEM: KEY_PEM,
            CONF_IP_ADDRESS: "192.168.1.10",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # A subsequent connection succeeds and the entry is created.
    async def _start() -> None:
        await set_connected(mock_mqtt_client, True)

    mock_mqtt_client.return_value.start.side_effect = _start

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERIAL: SERIAL,
            CONF_CERT_PEM: CERT_PEM,
            CONF_KEY_PEM: KEY_PEM,
            CONF_IP_ADDRESS: "192.168.1.10",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
