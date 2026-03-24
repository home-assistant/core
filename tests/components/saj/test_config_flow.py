"""Test the saj config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pysaj
import pytest

from homeassistant.components.saj.config_flow import CannotConnect
from homeassistant.components.saj.const import CONNECTION_TYPES, DOMAIN
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_IMPORT,
    SOURCE_REAUTH,
    SOURCE_USER,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import (
    MOCK_DHCP_DISCOVERY,
    MOCK_DHCP_DISCOVERY_ETHERNET,
    MOCK_DHCP_UNIQUE_ID,
    MOCK_DHCP_UNIQUE_ID_ALT,
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


async def test_form_wifi_open_network(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
) -> None:
    """Test WiFi without credentials when the device allows open access."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_USER_INPUT_WIFI[CONF_HOST],
            CONF_TYPE: MOCK_USER_INPUT_WIFI[CONF_TYPE],
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data[CONF_HOST] == MOCK_USER_INPUT_WIFI[CONF_HOST]
    assert result_data[CONF_TYPE] == MOCK_USER_INPUT_WIFI[CONF_TYPE]
    assert result_data[CONF_USERNAME] == ""
    assert result_data[CONF_PASSWORD] == ""
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_wifi_requires_credentials(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test WiFi flow when the first probe requires authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = MOCK_SERIAL_NUMBER
        saj_instance.read = AsyncMock(
            side_effect=[
                pysaj.UnauthorizedException("Auth required"),
                True,
            ]
        )
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
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

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = MOCK_SERIAL_NUMBER
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_NAME: "Roof Inverter",
                    CONF_USERNAME: MOCK_USER_INPUT_WIFI[CONF_USERNAME],
                    CONF_PASSWORD: MOCK_USER_INPUT_WIFI[CONF_PASSWORD],
                },
            )

    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Roof Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data == MOCK_USER_INPUT_WIFI
    assert result.get("result") is not None
    assert result["result"].unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_missing_serial_number(
    hass: HomeAssistant,
) -> None:
    """Test we reject devices that respond but do not expose a serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = None
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_USER_INPUT_ETHERNET,
            )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_form_wifi_probe_fails_shows_user_error(
    hass: HomeAssistant,
) -> None:
    """Test WiFi: failed probe (not SAJ / wrong host) keeps the user on host step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnexpectedResponseException("not a saj")
        )
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: MOCK_USER_INPUT_WIFI[CONF_HOST],
                    CONF_TYPE: MOCK_USER_INPUT_WIFI[CONF_TYPE],
                },
            )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


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
    assert result_entry.unique_id == MOCK_DHCP_UNIQUE_ID_ALT
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

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result.get("type") is FlowResultType.CREATE_ENTRY
        assert result.get("title") == "SAJ Solar Inverter"
        result_data = result.get("data")
        assert result_data is not None
        assert result_data[CONF_HOST] == DHCP_DISCOVERY.ip
        assert result_data[CONF_TYPE] == CONNECTION_TYPES[1]
        assert result_data[CONF_USERNAME] == ""
        assert result_data[CONF_PASSWORD] == ""
        result_entry = result.get("result")
        assert result_entry is not None
        assert result_entry.unique_id == MOCK_DHCP_UNIQUE_ID
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_pysaj")
async def test_dhcp_discovery_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test starting a flow by dhcp when already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SAJ Solar Inverter",
        unique_id=MOCK_DHCP_UNIQUE_ID_ALT,
        data={
            CONF_HOST: DHCP_DISCOVERY_ETHERNET.ip,
            CONF_TYPE: CONNECTION_TYPES[0],
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
        },
    )
    entry.add_to_hass(hass)
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
    """Test dhcp discovery aborts when hostname/MAC do not warrant a WiFi probe."""
    with patch(
        "homeassistant.components.saj.config_flow._validate_saj_device",
        side_effect=[CannotConnect("not saj")],
    ) as mock_validate:
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
    assert mock_validate.call_count == 1


async def test_dhcp_discovery_not_saj_device_after_wifi_probe(
    hass: HomeAssistant,
) -> None:
    """Test dhcp aborts when saj-* hostname justifies WiFi but both probes fail."""
    with patch(
        "homeassistant.components.saj.config_flow._validate_saj_device",
        side_effect=[CannotConnect("not saj"), CannotConnect("not saj")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=DhcpServiceInfo(
                ip="192.168.1.100",
                hostname="saj-unknown-oui",
                macaddress="aabbccddeeff",
            ),
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "not_saj_device"


async def test_dhcp_discovery_wifi_fallback_hostname_only_matcher(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """WiFi probe runs after ethernet fails when hostname matches saj-* (any OUI)."""
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
            data=DhcpServiceInfo(
                ip="192.168.1.150",
                hostname="saj-wifi-hostname",
                macaddress="aabbccddeeff",
            ),
        )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "confirm_discovery"
    assert mock_validate.call_count == 2
    assert len(mock_setup_entry.mock_calls) == 0

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_TYPE] == CONNECTION_TYPES[1]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_wifi_fallback_mac_oui_only(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """WiFi probe runs after ethernet fails when MAC matches SAJ OUI (any hostname)."""
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
            data=DhcpServiceInfo(
                ip="192.168.1.151",
                hostname="inverter-local",
                macaddress="441793aabbcc",
            ),
        )

    assert result.get("type") is FlowResultType.FORM
    assert mock_validate.call_count == 2

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_TYPE] == CONNECTION_TYPES[1]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_wifi_auth_challenge_confirm_only(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test DHCP WiFi when the device requires login: confirm-only, empty creds in data."""
    with patch(
        "homeassistant.components.saj.config_flow._validate_saj_device"
    ) as mock_validate:
        mock_validate.side_effect = [
            CannotConnect("Not ethernet"),
            (None, "SAJ Solar Inverter"),
        ]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "confirm_discovery"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    result_data = result.get("data")
    assert result_data is not None
    assert result_data[CONF_TYPE] == CONNECTION_TYPES[1]
    assert result_data[CONF_USERNAME] == ""
    assert result_data[CONF_PASSWORD] == ""


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

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result.get("type") is FlowResultType.CREATE_ENTRY
        result_data = result.get("data")
        assert result_data is not None
        assert result_data[CONF_TYPE] == CONNECTION_TYPES[1]
        assert result_data[CONF_USERNAME] == ""
        assert result_data[CONF_PASSWORD] == ""


async def test_reauth_updates_wifi_credentials(
    hass: HomeAssistant,
    mock_config_entry_wifi: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow updates Wi-Fi credentials."""
    mock_config_entry_wifi.add_to_hass(hass)

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": SOURCE_REAUTH,
                    "entry_id": mock_config_entry_wifi.entry_id,
                },
                data=mock_config_entry_wifi.data,
            )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "newuser",
                    CONF_PASSWORD: "newsecret",
                },
            )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    entry = hass.config_entries.async_get_entry(mock_config_entry_wifi.entry_id)
    assert entry is not None
    assert entry.data[CONF_USERNAME] == "newuser"
    assert entry.data[CONF_PASSWORD] == "newsecret"


async def test_import_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
) -> None:
    """Test YAML import creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.88",
            CONF_TYPE: CONNECTION_TYPES[0],
        },
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("result") is not None
    assert result["result"].unique_id == MOCK_SERIAL_NUMBER


async def test_import_invalid_auth(hass: HomeAssistant) -> None:
    """Test YAML import aborts when credentials are rejected."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnauthorizedException("auth failed")
        )
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_HOST: "192.168.1.88",
                    CONF_TYPE: CONNECTION_TYPES[1],
                    CONF_USERNAME: "u",
                    CONF_PASSWORD: "p",
                },
            )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "invalid_auth"


async def test_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test YAML import aborts when the inverter cannot be reached."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnexpectedResponseException("bad response")
        )
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_HOST: "192.168.1.88",
                    CONF_TYPE: CONNECTION_TYPES[0],
                },
            )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"
