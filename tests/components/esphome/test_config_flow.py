"""Test config flow."""
from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock, patch

from aioesphomeapi import (
    APIConnectionError,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    RequiresEncryptionAPIError,
    ResolveAPIError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
from homeassistant.components.esphome import CONF_NOISE_PSK, DOMAIN, DomainData
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MockDeviceInfo = namedtuple("DeviceInfo", ["uses_password", "name"])
VALID_NOISE_PSK = "bOFFzzvfpg5DB94DuBGLXD/hMnhpDKgP9UQyBulwWVU="
INVALID_NOISE_PSK = "lSYBYEjQI1bVL8s2Vask4YytGMj1f1epNtmoim2yuTM="


@pytest.fixture
def mock_client():
    """Mock APIClient."""
    with patch("homeassistant.components.esphome.config_flow.APIClient") as mock_client:

        def mock_constructor(
            host, port, password, zeroconf_instance=None, noise_psk=None
        ):
            """Fake the client constructor."""
            mock_client.host = host
            mock_client.port = port
            mock_client.password = password
            mock_client.zeroconf_instance = zeroconf_instance
            mock_client.noise_psk = noise_psk
            return mock_client

        mock_client.side_effect = mock_constructor
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()

        yield mock_client


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch("homeassistant.components.esphome.async_setup_entry", return_value=True):
        yield


async def test_user_connection_works(hass, mock_client, mock_zeroconf):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(False, "test"))

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 80},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 80,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
    }
    assert result["title"] == "test"
    assert result["result"].unique_id == "test"

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1
    assert mock_client.host == "127.0.0.1"
    assert mock_client.port == 80
    assert mock_client.password == ""
    assert mock_client.noise_psk is None


async def test_user_connection_updates_host(hass, mock_client, mock_zeroconf):
    """Test setup up the same name updates the host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="test",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(False, "test"))

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 80},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "127.0.0.1"


async def test_user_resolve_error(hass, mock_client, mock_zeroconf):
    """Test user step with IP resolve error."""

    with patch(
        "homeassistant.components.esphome.config_flow.APIConnectionError",
        new_callable=lambda: ResolveAPIError,
    ) as exc:
        mock_client.device_info.side_effect = exc
        result = await hass.config_entries.flow.async_init(
            "esphome",
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "resolve_error"}

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1


async def test_user_connection_error(hass, mock_client, mock_zeroconf):
    """Test user step with connection error."""
    mock_client.device_info.side_effect = APIConnectionError

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_error"}

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1


async def test_user_with_password(hass, mock_client, mock_zeroconf):
    """Test user step with password."""
    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(True, "test"))

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "password1"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "password1",
        CONF_NOISE_PSK: "",
    }
    assert mock_client.password == "password1"


async def test_user_invalid_password(hass, mock_client, mock_zeroconf):
    """Test user step with invalid password."""
    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(True, "test"))

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    mock_client.connect.side_effect = InvalidAuthAPIError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "invalid"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authenticate"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_login_connection_error(hass, mock_client, mock_zeroconf):
    """Test user step with connection error on login attempt."""
    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(True, "test"))

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    mock_client.connect.side_effect = APIConnectionError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "valid"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authenticate"
    assert result["errors"] == {"base": "connection_error"}


async def test_discovery_initiation(hass, mock_client, mock_zeroconf):
    """Test discovery importing works."""
    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(False, "test8266"))

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={},
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test8266"
    assert result["data"][CONF_HOST] == "192.168.43.183"
    assert result["data"][CONF_PORT] == 6053

    assert result["result"]
    assert result["result"].unique_id == "test8266"


async def test_discovery_already_configured_hostname(hass, mock_client):
    """Test discovery aborts if already configured via hostname."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test8266.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )

    entry.add_to_hass(hass)

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"


async def test_discovery_already_configured_ip(hass, mock_client):
    """Test discovery aborts if already configured via static IP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )

    entry.add_to_hass(hass)

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"address": "192.168.43.183"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"


async def test_discovery_already_configured_name(hass, mock_client):
    """Test discovery aborts if already configured via name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    mock_entry_data = MagicMock()
    mock_entry_data.device_info.name = "test8266"
    domain_data = DomainData.get(hass)
    domain_data.set_entry_data(entry, mock_entry_data)

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.184",
        addresses=["192.168.43.184"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"address": "test8266.local"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"
    assert entry.data[CONF_HOST] == "192.168.43.184"


async def test_discovery_duplicate_data(hass, mock_client):
    """Test discovery aborts if same mDNS packet arrives."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"address": "test8266.local"},
        type="mock_type",
    )

    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(False, "test8266"))

    result = await hass.config_entries.flow.async_init(
        "esphome", data=service_info, context={"source": config_entries.SOURCE_ZEROCONF}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_init(
        "esphome", data=service_info, context={"source": config_entries.SOURCE_ZEROCONF}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_discovery_updates_unique_id(hass, mock_client):
    """Test a duplicate discovery host aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )

    entry.add_to_hass(hass)

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"address": "test8266.local"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"


async def test_user_requires_psk(hass, mock_client, mock_zeroconf):
    """Test user step with requiring encryption key."""
    mock_client.device_info.side_effect = RequiresEncryptionAPIError

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["errors"] == {}

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1


async def test_encryption_key_valid_psk(hass, mock_client, mock_zeroconf):
    """Test encryption key step with valid key."""

    mock_client.device_info.side_effect = RequiresEncryptionAPIError

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "encryption_key"

    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(False, "test"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


async def test_encryption_key_invalid_psk(hass, mock_client, mock_zeroconf):
    """Test encryption key step with invalid key."""

    mock_client.device_info.side_effect = RequiresEncryptionAPIError

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "encryption_key"

    mock_client.device_info.side_effect = InvalidEncryptionKeyAPIError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: INVALID_NOISE_PSK}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["errors"] == {"base": "invalid_psk"}
    assert mock_client.noise_psk == INVALID_NOISE_PSK


async def test_reauth_initiation(hass, mock_client, mock_zeroconf):
    """Test reauth initiation shows form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_confirm_valid(hass, mock_client, mock_zeroconf):
    """Test reauth initiation with valid PSK."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )

    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(False, "test"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


async def test_reauth_confirm_invalid(hass, mock_client, mock_zeroconf):
    """Test reauth initiation with invalid PSK."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )

    mock_client.device_info.side_effect = InvalidEncryptionKeyAPIError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: INVALID_NOISE_PSK}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]
    assert result["errors"]["base"] == "invalid_psk"


async def test_discovery_dhcp_updates_host(hass, mock_client):
    """Test dhcp discovery updates host and aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    mock_entry_data = MagicMock()
    mock_entry_data.device_info.name = "test8266"
    domain_data = DomainData.get(hass)
    domain_data.set_entry_data(entry, mock_entry_data)

    service_info = dhcp.DhcpServiceInfo(
        ip="192.168.43.184",
        hostname="test8266",
        macaddress="00:00:00:00:00:00",
    )
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"
    assert entry.data[CONF_HOST] == "192.168.43.184"


async def test_discovery_dhcp_no_changes(hass, mock_client):
    """Test dhcp discovery updates host and aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    mock_entry_data = MagicMock()
    mock_entry_data.device_info.name = "test8266"
    domain_data = DomainData.get(hass)
    domain_data.set_entry_data(entry, mock_entry_data)

    service_info = dhcp.DhcpServiceInfo(
        ip="192.168.43.183",
        hostname="test8266",
        macaddress="00:00:00:00:00:00",
    )
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"
    assert entry.data[CONF_HOST] == "192.168.43.183"
