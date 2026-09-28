"""Test the Harbor config flow."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.harbor.const import (
    CONF_CERT_PEM,
    CONF_KEY_PEM,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import setup_integration
from .conftest import (
    CERT_PEM,
    DHCP_DISCOVERY,
    IP_ADDRESS,
    KEY_PEM,
    SERIAL,
    set_connected,
)

from tests.common import MockConfigEntry, get_schema_suggested_value

USER_INPUT = {
    CONF_SERIAL: SERIAL,
    CONF_CERT_PEM: CERT_PEM,
    CONF_KEY_PEM: KEY_PEM,
    CONF_IP_ADDRESS: IP_ADDRESS,
}
DISCOVERY_INPUT = {CONF_CERT_PEM: CERT_PEM, CONF_KEY_PEM: KEY_PEM}
NEW_IP_ADDRESS = "192.168.1.99"


@pytest.mark.parametrize(
    ("source", "discovery_info", "step_id", "description_placeholders", "user_input"),
    [
        pytest.param(SOURCE_USER, None, "user", None, USER_INPUT, id="user"),
        pytest.param(
            SOURCE_DHCP,
            DHCP_DISCOVERY,
            "discovery_confirm",
            {"serial": SERIAL},
            DISCOVERY_INPUT,
            id="dhcp",
        ),
    ],
)
async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mqtt_client: AsyncMock,
    source: str,
    discovery_info: DhcpServiceInfo | None,
    step_id: str,
    description_placeholders: dict[str, str] | None,
    user_input: dict[str, str],
) -> None:
    """Test the user and discovery flows both create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    assert result["description_placeholders"] == description_placeholders

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Camera {SERIAL}"
    assert result["result"].unique_id == SERIAL
    assert result["data"] == {
        CONF_SERIAL: SERIAL,
        CONF_CERT_PEM: CERT_PEM,
        CONF_KEY_PEM: KEY_PEM,
        CONF_IP_ADDRESS: IP_ADDRESS,
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
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nursery"


@pytest.mark.parametrize(
    ("source", "discovery_info", "valid_input"),
    [
        pytest.param(SOURCE_USER, None, USER_INPUT, id="user"),
        pytest.param(SOURCE_DHCP, DHCP_DISCOVERY, DISCOVERY_INPUT, id="dhcp"),
    ],
)
@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        pytest.param(CONF_CERT_PEM, "not a cert", "invalid_cert", id="bad_cert"),
        pytest.param(CONF_KEY_PEM, "not a key", "invalid_key", id="bad_key"),
    ],
)
@pytest.mark.usefixtures("mock_mqtt_client", "mock_setup_entry")
async def test_flow_invalid_credentials(
    hass: HomeAssistant,
    source: str,
    discovery_info: DhcpServiceInfo | None,
    valid_input: dict[str, str],
    field: str,
    value: str,
    error: str,
) -> None:
    """Test invalid credentials are surfaced and recoverable in both flows."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery_info
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**valid_input, field: value}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {field: error}
    # The PEM blobs are long, so the form is re-shown with what was entered.
    assert get_schema_suggested_value(result["data_schema"].schema, field) == value

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], valid_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "serial", ["123", "abcdefghij"], ids=["too_short", "non_digit"]
)
@pytest.mark.usefixtures("mock_mqtt_client", "mock_setup_entry")
async def test_user_flow_invalid_serial(hass: HomeAssistant, serial: str) -> None:
    """Test an invalid serial is surfaced and recoverable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_SERIAL: serial}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SERIAL: "invalid_serial"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
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
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("source", "discovery_info", "user_input"),
    [
        pytest.param(SOURCE_USER, None, USER_INPUT, id="user"),
        pytest.param(SOURCE_DHCP, DHCP_DISCOVERY, DISCOVERY_INPUT, id="dhcp"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_cannot_connect(
    hass: HomeAssistant,
    mock_mqtt_client: AsyncMock,
    source: str,
    discovery_info: DhcpServiceInfo | None,
    user_input: dict[str, str],
) -> None:
    """Test the flow shows an error and recovers when the camera is unreachable."""
    # Start the probe client without ever reporting a successful connection.
    mock_mqtt_client.return_value.start.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery_info
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # A subsequent connection succeeds and the entry is created.
    async def _start() -> None:
        await set_connected(mock_mqtt_client, True)

    mock_mqtt_client.return_value.start.side_effect = _start

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "hostname",
    ["harborc-123", "harborc-abcdefghij", "harborc-", "printer-1234567890"],
    ids=["short_serial", "non_digit_serial", "no_serial", "other_device"],
)
async def test_dhcp_flow_invalid_hostname(hass: HomeAssistant, hostname: str) -> None:
    """Test discovery aborts for hostnames that carry no Harbor serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=replace(DHCP_DISCOVERY, hostname=hostname),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_dhcp_flow_updates_ip_address(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test rediscovery of a known camera updates its stored IP address."""
    await setup_integration(hass, mock_config_entry)
    assert mock_mqtt_client.call_args.kwargs["config"].ip_address == IP_ADDRESS

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=replace(DHCP_DISCOVERY, ip=NEW_IP_ADDRESS),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_IP_ADDRESS] == NEW_IP_ADDRESS
    # The entry is reloaded so the camera is reached at its new address.
    assert mock_mqtt_client.call_args.kwargs["config"].ip_address == NEW_IP_ADDRESS


async def test_user_flow_aborts_while_discovery_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test adding a camera manually while its discovery is still pending."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
