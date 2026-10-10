"""Tests for the SMA Modbus config flow."""

from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusError
from sma_modbus import DeviceType, DiscoveryInfo, Vendor

from homeassistant.components.sma_modbus.const import (
    CONF_DEVICE_TYPE,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import HOST, SERIAL, UNIQUE_ID, mock_discovery_info

from tests.common import MockConfigEntry


def _zeroconf_info(
    host: str = HOST,
    hostname: str | None = None,
    port: int = 80,
) -> ZeroconfServiceInfo:
    """Build a ZeroconfServiceInfo for testing."""
    return ZeroconfServiceInfo(
        ip_address=host,
        ip_addresses=[host],
        hostname=hostname or f"SMA{SERIAL}.local",
        port=port,
        type="_http._tcp.local.",
        name="website for sma-inverter: sma*._http._tcp.local.",
        properties={},
    )


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test the user-initiated config flow succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.sma_modbus.config_flow._async_discover",
        AsyncMock(return_value=mock_discovery_info()),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: DEFAULT_PORT, CONF_UNIT_ID: 0},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT
    assert result["data"][CONF_DEVICE_TYPE] == DeviceType.SUNNY_BOY_SMART_ENERGY.value


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the user flow shows an error when discovery fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sma_modbus.config_flow._async_discover",
        AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: DEFAULT_PORT, CONF_UNIT_ID: 0},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test the user flow aborts when the device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={
            CONF_HOST: HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_DEVICE_TYPE: DeviceType.SUNNY_BOY_SMART_ENERGY.value,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sma_modbus.config_flow._async_discover",
        AsyncMock(return_value=mock_discovery_info()),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.178.50", CONF_PORT: DEFAULT_PORT, CONF_UNIT_ID: 0},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow_success(hass: HomeAssistant) -> None:
    """Test the zeroconf discovery flow succeeds."""
    with patch(
        "homeassistant.components.sma_modbus.config_flow._async_discover",
        AsyncMock(return_value=mock_discovery_info()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=_zeroconf_info(),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_TYPE] == DeviceType.SUNNY_BOY_SMART_ENERGY.value


async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test the zeroconf flow aborts when already configured and updates host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={
            CONF_HOST: HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_DEVICE_TYPE: DeviceType.SUNNY_BOY_SMART_ENERGY.value,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(host="192.168.178.50"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_no_serial_falls_through(hass: HomeAssistant) -> None:
    """Test the zeroconf flow falls through to manual setup without a serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(hostname="unknown.local"),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_zeroconf_serial_mismatch_falls_through(hass: HomeAssistant) -> None:
    """Test the zeroconf flow falls through when the discovered serial mismatches."""
    mismatch = mock_discovery_info()
    mismatch = DiscoveryInfo(
        device_type=mismatch.device_type,
        serial_number=99999999,
        unit_id=mismatch.unit_id,
        susy_id=mismatch.susy_id,
        modbus_profile_revision=mismatch.modbus_profile_revision,
        device_class=mismatch.device_class,
        device_model=mismatch.device_model,
        vendor=mismatch.vendor,
    )

    with patch(
        "homeassistant.components.sma_modbus.config_flow._async_discover",
        AsyncMock(return_value=mismatch),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=_zeroconf_info(),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_async_discover_returns_none_on_modbus_error(hass: HomeAssistant) -> None:
    """Test _async_discover returns None when the device raises ModbusError."""
    with patch(
        "homeassistant.components.sma_modbus.config_flow.async_get_temporary_unit",
        side_effect=ModbusError("connection refused"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: DEFAULT_PORT, CONF_UNIT_ID: 0},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_async_discover_returns_none_on_oserror(hass: HomeAssistant) -> None:
    """Test _async_discover returns None when the device raises OSError."""
    with patch(
        "homeassistant.components.sma_modbus.config_flow.async_get_temporary_unit",
        side_effect=OSError("network unreachable"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: DEFAULT_PORT, CONF_UNIT_ID: 0},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_with_unit_id(hass: HomeAssistant) -> None:
    """Test the user flow stores a non-default unit ID when provided."""
    info = DiscoveryInfo(
        device_type=DeviceType.SUNNY_BOY_SMART_ENERGY,
        serial_number=SERIAL,
        unit_id=5,
        susy_id=270,
        modbus_profile_revision=1140,
        device_class=8009,
        device_model=19085,
        vendor=Vendor.SMA.value,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sma_modbus.config_flow._async_discover",
        AsyncMock(return_value=info),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: DEFAULT_PORT, CONF_UNIT_ID: 5},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_UNIT_ID] == 5
