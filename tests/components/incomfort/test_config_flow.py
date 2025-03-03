"""Tests for the Intergas InComfort config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
from incomfortclient import InvalidGateway, InvalidHeaterList
import pytest

from homeassistant.components.incomfort.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import MOCK_CONFIG, MOCK_CONFIG_DHCP

from tests.common import MockConfigEntry

DHCP_SERVICE_INFO = DhcpServiceInfo(
    hostname="rfgateway",
    ip="192.168.1.12",
    macaddress="0004A3DEADFF",
)

DHCP_SERVICE_INFO_ALT = DhcpServiceInfo(
    hostname="rfgateway",
    ip="192.168.1.99",
    macaddress="0004A3DEADFF",
)


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_incomfort: MagicMock
) -> None:
    """Test we get the full form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Intergas InComfort/Intouch Lan2RF gateway"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_entry_already_configured(
    hass: HomeAssistant, mock_incomfort: MagicMock
) -> None:
    """Test aborting if the entry is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_CONFIG[CONF_HOST],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exc", "error", "base"),
    [
        (
            InvalidGateway,
            "auth_error",
            "base",
        ),
        (
            InvalidHeaterList,
            "no_heaters",
            "base",
        ),
        (
            ClientResponseError(None, None, status=500),
            "unknown",
            "base",
        ),
        (TimeoutError, "timeout_error", "base"),
        (ValueError, "unknown", "base"),
    ],
)
async def test_form_validation(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    exc: Exception,
    error: str,
    base: str,
) -> None:
    """Test form validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Simulate an issue
    mock_incomfort().heaters.side_effect = exc
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        base: error,
    }

    # Fix the issue and retry
    mock_incomfort().heaters.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "errors" not in result


async def test_dhcp_flow_simple(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test dhcp flow for older gateway without authentication needed.

    Assert on the creation of the gateway device, climate and boiler devices.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_SERVICE_INFO
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": "192.168.1.12"}

    config_entry: ConfigEntry = result["result"]
    entry_id = config_entry.entry_id

    await hass.async_block_till_done(wait_background_tasks=True)

    # Check the gateway device is discovered
    gateway_device = device_registry.async_get_device(identifiers={(DOMAIN, entry_id)})
    assert gateway_device is not None
    assert gateway_device.name == "RFGateway"
    assert gateway_device.manufacturer == "Intergas"
    assert gateway_device.connections == {("mac", "00:04:a3:de:ad:ff")}

    devices = device_registry.devices.get_devices_for_config_entry_id(entry_id)
    assert len(devices) == 3
    boiler_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "c0ffeec0ffee")}
    )
    assert boiler_device.via_device_id == gateway_device.id
    assert boiler_device is not None
    climate_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "c0ffeec0ffee_1")}
    )
    assert climate_device is not None
    assert climate_device.via_device_id == gateway_device.id

    # Check the host is dynamically updated
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_SERVICE_INFO_ALT
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == DHCP_SERVICE_INFO_ALT.ip


async def test_dhcp_flow_migrates_existing_entry_without_unique_id(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test dhcp flow migrates an existing entry without unique_id."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_SERVICE_INFO
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Check the gateway device is discovered after a reload
    # And has updated connections
    gateway_device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert gateway_device is not None
    assert gateway_device.name == "RFGateway"
    assert gateway_device.manufacturer == "Intergas"
    assert gateway_device.connections == {("mac", "00:04:a3:de:ad:ff")}

    devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_config_entry.entry_id
    )
    assert len(devices) == 3
    boiler_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "c0ffeec0ffee")}
    )
    assert boiler_device.via_device_id == gateway_device.id
    assert boiler_device is not None
    climate_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "c0ffeec0ffee_1")}
    )
    assert climate_device is not None
    assert climate_device.via_device_id == gateway_device.id


async def test_dhcp_flow_wih_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_incomfort: MagicMock
) -> None:
    """Test dhcp flow for with authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_SERVICE_INFO
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    # Try again, but now with the correct host, but still with an auth error
    with patch.object(
        mock_incomfort(),
        "heaters",
        side_effect=InvalidGateway,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.12"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_auth"
    assert result["errors"] == {"base": "auth_error"}

    # Submit the form with added credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG_DHCP
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Intergas InComfort/Intouch Lan2RF gateway"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the re-authentication flow succeeds."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_failure(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the re-authentication flow fails."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch.object(
        mock_incomfort(),
        "heaters",
        side_effect=InvalidGateway,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "incorrect-password"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the re-configure flow succeeds."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG | {CONF_PASSWORD: "new-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_failure(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the re-configure flow fails."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch.object(
        mock_incomfort(),
        "heaters",
        side_effect=InvalidGateway,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_CONFIG | {CONF_PASSWORD: "wrong-password"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG | {CONF_PASSWORD: "new-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("user_input", "legacy_setpoint_status"),
    [
        ({}, False),
        ({"legacy_setpoint_status": False}, False),
        ({"legacy_setpoint_status": True}, True),
    ],
)
async def test_options_flow(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    user_input: dict[str, Any],
    legacy_setpoint_status: bool,
) -> None:
    """Test options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch("homeassistant.components.incomfort.async_setup_entry") as restart_mock:
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert restart_mock.call_count == 1

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {"legacy_setpoint_status": legacy_setpoint_status}
    assert entry.options.get("legacy_setpoint_status", False) is legacy_setpoint_status
