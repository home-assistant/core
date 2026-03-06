"""Test the Casper Glow config flow."""

from unittest.mock import patch

from bluetooth_data_tools import human_readable_name
from pycasperglow import CasperGlowError

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.casper_glow.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac

from . import CASPER_GLOW_DISCOVERY_INFO, NOT_CASPER_GLOW_DISCOVERY_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device


async def test_bluetooth_step_success(hass: HomeAssistant) -> None:
    """Test bluetooth discovery step success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=CASPER_GLOW_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        ),
        patch(
            "homeassistant.components.casper_glow.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == human_readable_name(
        None, CASPER_GLOW_DISCOVERY_INFO.name, CASPER_GLOW_DISCOVERY_INFO.address
    )
    assert result2["data"] == {
        CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
    }
    assert result2["result"].unique_id == format_mac(CASPER_GLOW_DISCOVERY_INFO.address)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """Test bluetooth confirm step when device cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=CASPER_GLOW_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        side_effect=CasperGlowError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bluetooth_confirm"
    assert result2["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        ),
        patch(
            "homeassistant.components.casper_glow.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_confirm_unknown_error(hass: HomeAssistant) -> None:
    """Test bluetooth confirm step with an unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=CASPER_GLOW_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        side_effect=RuntimeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bluetooth_confirm"
    assert result2["errors"] == {"base": "unknown"}

    with (
        patch(
            "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        ),
        patch(
            "homeassistant.components.casper_glow.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test user step success path."""
    with patch(
        "homeassistant.components.casper_glow.config_flow.async_discovered_service_info",
        return_value=[NOT_CASPER_GLOW_DISCOVERY_INFO, CASPER_GLOW_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        ),
        patch(
            "homeassistant.components.casper_glow.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == human_readable_name(
        None, CASPER_GLOW_DISCOVERY_INFO.name, CASPER_GLOW_DISCOVERY_INFO.address
    )
    assert result2["data"] == {
        CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
    }
    assert result2["result"].unique_id == format_mac(CASPER_GLOW_DISCOVERY_INFO.address)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_no_devices(hass: HomeAssistant) -> None:
    """Test user step with no devices found."""
    with patch(
        "homeassistant.components.casper_glow.config_flow.async_discovered_service_info",
        return_value=[NOT_CASPER_GLOW_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step when device cannot connect."""
    with patch(
        "homeassistant.components.casper_glow.config_flow.async_discovered_service_info",
        return_value=[CASPER_GLOW_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        side_effect=CasperGlowError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        ),
        patch(
            "homeassistant.components.casper_glow.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == human_readable_name(
        None, CASPER_GLOW_DISCOVERY_INFO.name, CASPER_GLOW_DISCOVERY_INFO.address
    )
    assert result3["data"] == {
        CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_unknown_error(hass: HomeAssistant) -> None:
    """Test user step with an unknown exception."""
    with patch(
        "homeassistant.components.casper_glow.config_flow.async_discovered_service_info",
        return_value=[CASPER_GLOW_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        side_effect=RuntimeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}

    with (
        patch(
            "homeassistant.components.casper_glow.config_flow.CasperGlow.handshake",
        ),
        patch(
            "homeassistant.components.casper_glow.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == human_readable_name(
        None, CASPER_GLOW_DISCOVERY_INFO.name, CASPER_GLOW_DISCOVERY_INFO.address
    )
    assert result3["data"] == {
        CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test already configured device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address,
        },
        unique_id=format_mac(CASPER_GLOW_DISCOVERY_INFO.address),
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=CASPER_GLOW_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_skips_unrecognized_device(hass: HomeAssistant) -> None:
    """Test that devices with neither a matching UUID nor a matching name are skipped."""
    unrecognized_discovery = BluetoothServiceInfoBleak(
        name=None,
        address="AA:BB:CC:DD:EE:11",
        rssi=-60,
        manufacturer_data={},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:11", name=None),
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
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
