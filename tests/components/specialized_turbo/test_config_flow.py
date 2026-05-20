"""Tests for Specialized Turbo config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BleakError
import pytest

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.specialized_turbo.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_ADDRESS,
    MOCK_ADDRESS_FORMATTED,
    MOCK_NAME,
    MOCK_TCU1_ADDRESS,
    MOCK_TCU1_ADDRESS_FORMATTED,
    TCU1_SERVICE_INFO,
    TCX_SERVICE_INFO,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_ble_connection")
async def test_bluetooth_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth discovery creates entry on successful connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCX_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == {CONF_ADDRESS: MOCK_ADDRESS}
    assert result["result"].unique_id == MOCK_ADDRESS_FORMATTED
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test bluetooth discovery aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCX_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (None, "cannot_connect"),
        (BleakError("fail"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
    ],
    ids=["no_device", "bleak_error", "timeout"],
)
async def test_bluetooth_confirm_connection_errors(
    hass: HomeAssistant, side_effect: Exception | None, error: str
) -> None:
    """Test bluetooth confirm shows error on connection failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCX_SERVICE_INFO,
    )
    ble_device = MagicMock() if side_effect is not None else None
    with (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
            side_effect=side_effect,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.usefixtures("mock_ble_connection")
async def test_bluetooth_confirm_recover_from_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that after a connection error, user can retry successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCX_SERVICE_INFO,
    )
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_ble_connection")
async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test user-initiated flow with discovered devices."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[TCX_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: MOCK_ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: MOCK_ADDRESS}
    assert result["result"].unique_id == MOCK_ADDRESS_FORMATTED


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Test user flow aborts when no devices are found."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow filters out already configured devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[TCX_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    ("service_info", "expected_address", "expected_unique_id"),
    [
        (TCX_SERVICE_INFO, MOCK_ADDRESS, MOCK_ADDRESS_FORMATTED),
        (TCU1_SERVICE_INFO, MOCK_TCU1_ADDRESS, MOCK_TCU1_ADDRESS_FORMATTED),
    ],
    ids=["tcx", "tcu1"],
)
@pytest.mark.usefixtures("mock_ble_connection")
async def test_bluetooth_discovery_by_generation(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    service_info: BluetoothServiceInfoBleak,
    expected_address: str,
    expected_unique_id: str,
) -> None:
    """Test bluetooth discovery works for both TCX and TCU1 bikes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == expected_address
    assert result["result"].unique_id == expected_unique_id
