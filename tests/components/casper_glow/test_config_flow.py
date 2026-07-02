"""Test the Casper Glow config flow."""

from unittest.mock import MagicMock, patch

from bluetooth_data_tools import human_readable_name
from pycasperglow import CasperGlowError
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.casper_glow.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac

from . import CASPER_GLOW_DISCOVERY_INFO, NOT_CASPER_GLOW_DISCOVERY_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)


async def test_bluetooth_step_success(
    hass: HomeAssistant, mock_casper_glow: MagicMock
) -> None:
    """Test bluetooth discovery step success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=CASPER_GLOW_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Inject before configure so async_setup_entry can find the device via
    # async_ble_device_from_address. The unique_id is already claimed by our
    # flow so the BT manager's auto-started flow will abort as a duplicate.
    inject_bluetooth_service_info(hass, CASPER_GLOW_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == human_readable_name(
        None, CASPER_GLOW_DISCOVERY_INFO.name, CASPER_GLOW_DISCOVERY_INFO.address
    )
    assert result["data"] == {
        CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
    }
    assert result["result"].unique_id == format_mac(CASPER_GLOW_DISCOVERY_INFO.address)


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [(CasperGlowError, "cannot_connect"), (RuntimeError, "unknown")],
)
async def test_bluetooth_confirm_error(
    hass: HomeAssistant,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test bluetooth confirm step error handling."""
    with patch(
        "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=CASPER_GLOW_DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_user_step_success(
    hass: HomeAssistant, mock_casper_glow: MagicMock
) -> None:
    """Test user step success path."""
    with patch(
        "homeassistant.components.casper_glow.config_flow.async_discovered_service_info",
        return_value=[NOT_CASPER_GLOW_DISCOVERY_INFO, CASPER_GLOW_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Inject before configure so async_setup_entry can find the device via
    # async_ble_device_from_address.
    inject_bluetooth_service_info(hass, CASPER_GLOW_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == human_readable_name(
        None, CASPER_GLOW_DISCOVERY_INFO.name, CASPER_GLOW_DISCOVERY_INFO.address
    )
    assert result["data"] == {
        CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
    }
    assert result["result"].unique_id == format_mac(CASPER_GLOW_DISCOVERY_INFO.address)


async def test_user_step_no_devices(hass: HomeAssistant) -> None:
    """Test user step with no devices found."""
    with patch(
        "homeassistant.components.casper_glow.config_flow.async_discovered_service_info",
        return_value=[NOT_CASPER_GLOW_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [(CasperGlowError, "cannot_connect"), (RuntimeError, "unknown")],
)
async def test_user_step_error(
    hass: HomeAssistant,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test user step error handling."""
    with patch(
        "homeassistant.components.casper_glow.config_flow.async_discovered_service_info",
        return_value=[CASPER_GLOW_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test already configured device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=CASPER_GLOW_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_skips_unrecognized_device(hass: HomeAssistant) -> None:
    """Test that devices without a matching local name prefix are skipped."""
    unrecognized_discovery = BluetoothServiceInfoBleak(
        name="",
        address="AA:BB:CC:DD:EE:11",
        rssi=-60,
        manufacturer_data={},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:11", name=""),
        advertisement=generate_advertisement_data(service_uuids=[]),
        time=0,
        connectable=True,
        tx_power=-127,
    )
    with patch(
        "homeassistant.components.casper_glow.config_flow.async_discovered_service_info",
        return_value=[unrecognized_discovery],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
