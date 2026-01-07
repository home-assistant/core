"""Test the saj config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pysaj
import pytest

from homeassistant.components.saj.config_flow import CannotConnect
from homeassistant.components.saj.const import CONNECTION_TYPES, DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TYPE, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import (
    MOCK_DHCP_DISCOVERY,
    MOCK_DHCP_DISCOVERY_ETHERNET,
    MOCK_MAC_ADDRESS,
    MOCK_MAC_ADDRESS_FORMATTED,
    MOCK_SERIAL_NUMBER,
    MOCK_USER_INPUT_ETHERNET,
    MOCK_USER_INPUT_WIFI,
)

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    ip=MOCK_DHCP_DISCOVERY["ip"],
    hostname=MOCK_DHCP_DISCOVERY["hostname"],
    macaddress=MOCK_DHCP_DISCOVERY["macaddress"],
)

DHCP_DISCOVERY_ETHERNET = DhcpServiceInfo(
    ip=MOCK_DHCP_DISCOVERY_ETHERNET["ip"],
    hostname=MOCK_DHCP_DISCOVERY_ETHERNET["hostname"],
    macaddress=MOCK_DHCP_DISCOVERY_ETHERNET["macaddress"],
)

DHCP_DISCOVERY_NEW_IP = DhcpServiceInfo(
    ip="192.168.1.200",
    hostname="saj-test-device-001",
    macaddress="441793aabbcc",
)


async def test_form_ethernet(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
) -> None:
    """Test we get the form for ethernet connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_INPUT_ETHERNET,
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data[CONF_HOST] == MOCK_USER_INPUT_ETHERNET[CONF_HOST]
    assert result_data[CONF_TYPE] == MOCK_USER_INPUT_ETHERNET[CONF_TYPE]
    assert result_data.get(CONF_USERNAME, "") == ""
    assert result_data.get(CONF_PASSWORD, "") == ""
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_wifi(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
) -> None:
    """Test we get the form for wifi connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") is None

    # Step 1: Submit host and type (WiFi)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_USER_INPUT_WIFI[CONF_HOST],
            CONF_TYPE: MOCK_USER_INPUT_WIFI[CONF_TYPE],
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "device_credentials"
    assert result.get("errors") is None

    # Step 2: Submit WiFi credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: MOCK_USER_INPUT_WIFI[CONF_USERNAME],
            CONF_PASSWORD: MOCK_USER_INPUT_WIFI[CONF_PASSWORD],
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data == MOCK_USER_INPUT_WIFI
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (pysaj.UnexpectedResponseException("Connection failed"), "cannot_connect"),
        (pysaj.UnauthorizedException("Auth failed"), "cannot_connect"),
        (Exception("Unknown error"), "cannot_connect"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle exceptions during form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(side_effect=exception)
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_USER_INPUT_ETHERNET,
            )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": error}


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
) -> None:
    """Test starting a flow by user when already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_INPUT_ETHERNET, unique_id=MOCK_SERIAL_NUMBER
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = MOCK_SERIAL_NUMBER
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=MOCK_USER_INPUT_ETHERNET,
            )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_dhcp_discovery_ethernet(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
) -> None:
    """Test we can setup from dhcp discovery for ethernet device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY_ETHERNET,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "confirm_discovery"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data[CONF_HOST] == DHCP_DISCOVERY_ETHERNET.ip
    assert result_data[CONF_TYPE] == CONNECTION_TYPES[0]
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_wifi(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj_wifi: MagicMock
) -> None:
    """Test we can setup from dhcp discovery for wifi device."""
    # Mock ethernet validation to fail, then wifi to succeed
    with patch(
        "homeassistant.components.saj.config_flow._validate_saj_device"
    ) as mock_validate:
        # First call (ethernet) fails, second call (wifi) succeeds
        mock_validate.side_effect = [
            CannotConnect("Not ethernet"),
            (MOCK_SERIAL_NUMBER, "SAJ Solar Inverter"),
        ]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "confirm_discovery"

        # WiFi devices need credentials - mock validation in confirm step
        with patch("pysaj.SAJ") as saj_cls:
            saj_instance = MagicMock()
            saj_instance.serialnumber = MOCK_SERIAL_NUMBER
            saj_instance.read = AsyncMock(return_value=True)
            saj_cls.return_value = saj_instance

            with patch("pysaj.Sensors"):
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    {
                        CONF_USERNAME: "admin",
                        CONF_PASSWORD: "password",
                    },
                )

        assert result.get("type") is FlowResultType.CREATE_ENTRY
        assert result.get("title") == "SAJ Solar Inverter"
        result_data = result.get("data")
        assert result_data is not None
        assert result_data[CONF_HOST] == DHCP_DISCOVERY.ip
        assert result_data[CONF_TYPE] == CONNECTION_TYPES[1]
        assert result_data[CONF_USERNAME] == "admin"
        assert result_data[CONF_PASSWORD] == "password"
        result_entry = result.get("result")
        assert result_entry is not None
        assert result_entry.unique_id == MOCK_SERIAL_NUMBER
        assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
    mock_pysaj: MagicMock,
) -> None:
    """Test starting a flow by dhcp when already configured."""
    mock_config_entry_ethernet.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY_ETHERNET
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_dhcp_discovery_ip_update(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
    mock_pysaj: MagicMock,
) -> None:
    """Test dhcp discovery updates IP address for existing device."""
    mock_config_entry_ethernet.add_to_hass(hass)
    old_ip = mock_config_entry_ethernet.data[CONF_HOST]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY_NEW_IP
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_config_entry_ethernet.data[CONF_HOST] == DHCP_DISCOVERY_NEW_IP.ip
    assert mock_config_entry_ethernet.data[CONF_HOST] != old_ip


async def test_dhcp_discovery_existing_device_connection_type(
    hass: HomeAssistant,
    mock_config_entry_wifi: MockConfigEntry,
    mock_pysaj_wifi: MagicMock,
) -> None:
    """Test dhcp discovery uses existing device connection type."""
    mock_config_entry_wifi.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_wifi.entry_id)
    await hass.async_block_till_done()

    # Create device registry entry with MAC
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry_wifi.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(MOCK_MAC_ADDRESS))},
    )

    # Simulate DHCP discovery with new IP
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.200",
            hostname="saj-test-device-001",
            macaddress=MOCK_MAC_ADDRESS_FORMATTED,
        ),
    )

    # Should update IP and use existing connection type (WiFi)
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_config_entry_wifi.data[CONF_HOST] == "192.168.1.200"
    assert mock_config_entry_wifi.data[CONF_TYPE] == CONNECTION_TYPES[1]


async def test_dhcp_discovery_not_saj_device(
    hass: HomeAssistant,
) -> None:
    """Test dhcp discovery aborts for non-SAJ device."""
    # Device with non-matching hostname and MAC
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            hostname="other-device",
            macaddress="aabbccddeeff",
        ),
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "not_saj_device"


async def test_dhcp_discovery_wifi_auth_error(
    hass: HomeAssistant,
    mock_pysaj_wifi: MagicMock,
) -> None:
    """Test dhcp discovery handles WiFi authentication errors."""
    with patch(
        "homeassistant.components.saj.config_flow._validate_saj_device"
    ) as mock_validate:
        # Ethernet fails, WiFi validation fails with auth error (which becomes CannotConnect)
        mock_validate.side_effect = [
            CannotConnect("Not ethernet"),
            CannotConnect(
                "Authentication required"
            ),  # UnauthorizedException becomes CannotConnect
        ]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

        # When both validations fail, it should abort
        assert result.get("type") is FlowResultType.ABORT
        assert result.get("reason") == "not_saj_device"


async def test_confirm_discovery_ethernet(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
) -> None:
    """Test confirmation step for ethernet discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY_ETHERNET,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "confirm_discovery"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    result_data = result.get("data")
    assert result_data is not None
    assert result_data[CONF_TYPE] == CONNECTION_TYPES[0]


async def test_confirm_discovery_wifi(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj_wifi: MagicMock
) -> None:
    """Test confirmation step for wifi discovery."""
    with patch(
        "homeassistant.components.saj.config_flow._validate_saj_device"
    ) as mock_validate:
        mock_validate.side_effect = [
            CannotConnect("Not ethernet"),
            (MOCK_SERIAL_NUMBER, "SAJ Solar Inverter"),
        ]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "confirm_discovery"

        # Mock the validation in confirm step
        with patch("pysaj.SAJ") as saj_cls:
            saj_instance = MagicMock()
            saj_instance.serialnumber = MOCK_SERIAL_NUMBER
            saj_instance.read = AsyncMock(return_value=True)
            saj_cls.return_value = saj_instance

            with patch("pysaj.Sensors"):
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    {
                        CONF_USERNAME: "admin",
                        CONF_PASSWORD: "password",
                    },
                )

        assert result.get("type") is FlowResultType.CREATE_ENTRY
        result_data = result.get("data")
        assert result_data is not None
        assert result_data[CONF_TYPE] == CONNECTION_TYPES[1]
        assert result_data[CONF_USERNAME] == "admin"
        assert result_data[CONF_PASSWORD] == "password"
