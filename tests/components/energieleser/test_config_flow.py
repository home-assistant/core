"""Tests for the energieleser config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from energieleser import (
    EnergieleserConnectionError,
    EnergieleserError,
    EnergieleserUnknownDeviceError,
    GasleserDevice,
)
import pytest

from homeassistant.components.energieleser.const import CONF_SW_VERSION, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import GASLESER_DEVICE_ID, STROMLESER_DEVICE_ID, STROMLESER_SW_VERSION

from tests.common import MockConfigEntry


def _stromleser_zeroconf(ip: str = "192.168.1.100") -> ZeroconfServiceInfo:
    """Build zeroconf discovery info for a stromleser device.

    The hostname encodes the device id (``strom-one-8529546829`` →
    ``STROM_ONE_8529546829``) and the TXT records carry the firmware version.
    """
    return ZeroconfServiceInfo(
        ip_address=ip_address(ip),
        ip_addresses=[ip_address(ip)],
        hostname="strom-one-8529546829.local.",
        name="Stromleser One - strom-one-8529546829",
        port=80,
        properties={"version": STROMLESER_SW_VERSION},
        type="_stromleser._tcp.local.",
    )


@pytest.mark.usefixtures("mock_setup_entry", "mock_energieleser_client")
async def test_user_flow_stromleser(hass: HomeAssistant) -> None:
    """Test a successful manual user flow for a stromleser device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "stromleser.one"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_DEVICE_ID] == STROMLESER_DEVICE_ID
    assert result["result"].unique_id == STROMLESER_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_gasleser(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_gasleser_device: GasleserDevice,
) -> None:
    """Test a successful manual user flow for a gasleser device."""
    mock_energieleser_client.get_device.return_value = mock_gasleser_device

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.101"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["device_id"] == GASLESER_DEVICE_ID
    assert result["result"].unique_id == GASLESER_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(
            EnergieleserConnectionError("boom"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            EnergieleserUnknownDeviceError("FOO_0000000001"),
            "unknown_device_type",
            id="unknown_device_type",
        ),
        pytest.param(
            EnergieleserError("boom"),
            "unknown",
            id="unknown",
        ),
    ],
)
async def test_user_flow_client_errors(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test client errors during the user flow."""
    mock_energieleser_client.get_device.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.99"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


@pytest.mark.usefixtures("mock_setup_entry", "mock_energieleser_client")
async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test that a duplicate device is aborted."""
    mock_stromleser_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_energieleser_client")
async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test a successful zeroconf discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_stromleser_zeroconf(),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["device_type"] == "stromleser.one"
    assert result["description_placeholders"][CONF_DEVICE_ID] == STROMLESER_DEVICE_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "stromleser.one"
    assert result["data"][CONF_DEVICE_ID] == STROMLESER_DEVICE_ID
    assert result["data"][CONF_SW_VERSION] == STROMLESER_SW_VERSION


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
) -> None:
    """Test a zeroconf flow aborts and refreshes host/version for a known device."""
    entry = MockConfigEntry(
        title=STROMLESER_DEVICE_ID,
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_DEVICE_ID: STROMLESER_DEVICE_ID,
            CONF_SW_VERSION: "v1.0.0-old",
        },
        unique_id=STROMLESER_DEVICE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_stromleser_zeroconf("192.168.1.200"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # The device id comes from the discovery hostname, so the flow aborts before
    # contacting the device while still refreshing the stored host and firmware.
    mock_energieleser_client.get_device.assert_not_called()
    assert entry.data[CONF_HOST] == "192.168.1.200"
    assert entry.data[CONF_SW_VERSION] == STROMLESER_SW_VERSION


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("service_type", "hostname", "device_id"),
    [
        pytest.param(
            "_stromleser._tcp.local.",
            "strom-one-2429489063.local.",
            "STROM_ONE_2429489063",
            id="stromleser",
        ),
        pytest.param(
            "_gasleser._tcp.local.",
            "gas-4224559459.local.",
            "GAS_4224559459",
            id="gasleser",
        ),
        pytest.param(
            "_wasserleser._tcp.local.",
            "wasser-6940014409.local.",
            "WASSER_6940014409",
            id="wasserleser",
        ),
        pytest.param(
            "_waermeleser._tcp.local.",
            "heat-8413853965.local.",
            "HEAT_8413853965",
            id="waermeleser",
        ),
    ],
)
async def test_zeroconf_device_id_derived_from_hostname(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    service_type: str,
    hostname: str,
    device_id: str,
) -> None:
    """Test the unique id comes from the stable hostname, not the friendly name.

    The mDNS friendly name differs per family and even changes across firmware
    versions, so the hostname is the only reliable source for the device id.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_DEVICE_ID: device_id},
        unique_id=device_id,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.200"),
            ip_addresses=[ip_address("192.168.1.200")],
            hostname=hostname,
            name="Unrelated Friendly Name",
            port=80,
            properties={},
            type=service_type,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Matching on the hostname-derived id aborts before any network call, even
    # though the friendly name is unrelated to the device id.
    mock_energieleser_client.get_device.assert_not_called()
    assert entry.data[CONF_HOST] == "192.168.1.200"


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        pytest.param(
            EnergieleserConnectionError("boom"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            EnergieleserUnknownDeviceError("FOO_0000000001"),
            "unknown_device_type",
            id="unknown_device_type",
        ),
        pytest.param(
            EnergieleserError("boom"),
            "unknown",
            id="unknown",
        ),
    ],
)
async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    side_effect: Exception,
    expected_reason: str,
) -> None:
    """Test that a zeroconf flow aborts on client errors."""
    mock_energieleser_client.get_device.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_stromleser_zeroconf(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.usefixtures("mock_setup_entry", "mock_energieleser_client")
async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test a successful reconfiguration flow."""
    mock_stromleser_config_entry.add_to_hass(hass)

    result = await mock_stromleser_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.102"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_stromleser_config_entry.data[CONF_HOST] == "192.168.1.102"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_another_device(
    hass: HomeAssistant,
    mock_stromleser_config_entry: MockConfigEntry,
    mock_energieleser_client: AsyncMock,
    mock_gasleser_device: GasleserDevice,
) -> None:
    """Test reconfiguration flow with a different device."""
    mock_stromleser_config_entry.add_to_hass(hass)

    mock_energieleser_client.get_device.return_value = mock_gasleser_device

    result = await mock_stromleser_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.105"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(
            EnergieleserConnectionError("boom"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            EnergieleserUnknownDeviceError("FOO_0000000001"),
            "unknown_device_type",
            id="unknown_device_type",
        ),
        pytest.param(
            EnergieleserError("boom"),
            "unknown",
            id="unknown",
        ),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_stromleser_config_entry: MockConfigEntry,
    mock_energieleser_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test client errors during reconfiguration flow."""
    mock_stromleser_config_entry.add_to_hass(hass)
    mock_energieleser_client.get_device.side_effect = side_effect

    result = await mock_stromleser_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.105"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_energieleser_client.get_device.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.102"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
