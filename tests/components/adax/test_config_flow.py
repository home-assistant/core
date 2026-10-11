"""Test the Adax config flow."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import adax_local
import aiohttp
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
import pytest

from homeassistant import config_entries
from homeassistant.components.adax.config_flow import is_adax_tls_device
from homeassistant.components.adax.const import (
    ACCOUNT_ID,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
    WIFI_PSWD,
    WIFI_SSID,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry

TEST_DATA = {
    ACCOUNT_ID: 12345,
    CONF_PASSWORD: "pswd",
}

DHCP_DISCOVERY_INFO = DhcpServiceInfo(
    ip="192.168.1.9",
    macaddress="7c2c67ecf7d4",
    hostname="heater",
)
TEST_DHCP_UNIQUE_ID = str(int("7c2c67ecf7d4", 16))


def _generate_test_der_cert(common_name: str) -> bytes:
    """Generate a minimal self-signed DER certificate with a specific CN."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(Encoding.DER)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    with (
        patch(
            "adax.get_adax_token",
            return_value="test_token",
        ),
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == str(TEST_DATA["account_id"])
    assert result3["data"] == {
        ACCOUNT_ID: TEST_DATA["account_id"],
        CONF_PASSWORD: TEST_DATA["password"],
        CONNECTION_TYPE: CLOUD,
    }
    assert result3["result"].unique_id == str(TEST_DATA["account_id"])
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    with patch(
        "adax.get_adax_token",
        return_value=None,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            TEST_DATA,
        )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "adax.get_adax_token",
            return_value="test_token",
        ),
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""

    first_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        unique_id=str(TEST_DATA[ACCOUNT_ID]),
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    with patch("adax.get_adax_token", return_value="token"):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


# local API:


async def test_local_create_entry(hass: HomeAssistant) -> None:
    """Test create entry from user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with (
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.adax.config_flow.adax_local.AdaxConfig",
            autospec=True,
        ) as mock_client_class,
    ):
        client = mock_client_class.return_value
        client.configure_device.return_value = True
        client.device_ip = "192.168.1.4"
        client.access_token = "token"
        client.mac_id = "8383838"
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    test_data[CONNECTION_TYPE] = LOCAL
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "8383838"
    assert result["data"] == {
        "connection_type": "Local",
        "ip_address": "192.168.1.4",
        "token": "token",
        "unique_id": "8383838",
    }


async def test_local_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    first_entry = MockConfigEntry(
        domain=DOMAIN,
        data=test_data,
        unique_id="8383838",
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch("adax_local.AdaxConfig", autospec=True) as mock_client_class:
        client = mock_client_class.return_value
        client.configure_device.return_value = True
        client.device_ip = "192.168.1.4"
        client.access_token = "token"
        client.mac_id = "8383838"

        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_local_connection_error(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch(
        "homeassistant.components.adax.config_flow.adax_local.AdaxConfig.configure_device",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.adax.config_flow.adax_local.AdaxConfig",
            autospec=True,
        ) as mock_client_class,
    ):
        client = mock_client_class.return_value
        client.configure_device.return_value = True
        client.device_ip = "192.168.1.4"
        client.access_token = "token"
        client.mac_id = "8383838"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            test_data,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_local_heater_not_available(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch(
        "homeassistant.components.adax.config_flow.adax_local.AdaxConfig.configure_device",
        side_effect=adax_local.HeaterNotAvailable,
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "heater_not_available"


async def test_local_heater_not_found(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch(
        "homeassistant.components.adax.config_flow.adax_local.AdaxConfig.configure_device",
        side_effect=adax_local.HeaterNotFound,
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "heater_not_found"


async def test_local_invalid_wifi_cred(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch(
        "homeassistant.components.adax.config_flow.adax_local.AdaxConfig.configure_device",
        side_effect=adax_local.InvalidWifiCred,
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_dhcp_discovery_flow_success(hass: HomeAssistant) -> None:
    """Test successful setup initiated via DHCP discovery."""
    with (
        patch(
            "homeassistant.components.adax.config_flow.is_adax_tls_device",
            return_value=True,
        ),
        patch(
            "homeassistant.components.adax.config_flow.AdaxLocal.get_status",
            new_callable=AsyncMock,
            return_value={"current_temperature": 21.5},
        ),
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY_INFO,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "dhcp_confirm"

        flow = hass.config_entries.flow.async_get(result["flow_id"])
        assert flow["context"]["title_placeholders"] == {
            "ip_address": "192.168.1.9",
        }
        assert result["description_placeholders"] == {
            "ip_address": "192.168.1.9",
            "mac": "7c:2c:67:ec:f7:d4",
        }

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: "valid_secret_token"},
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["result"].unique_id == TEST_DHCP_UNIQUE_ID
        assert result2["title"] == TEST_DHCP_UNIQUE_ID
        assert result2["data"] == {
            CONF_IP_ADDRESS: "192.168.1.9",
            CONF_TOKEN: "valid_secret_token",
            CONF_UNIQUE_ID: TEST_DHCP_UNIQUE_ID,
            CONNECTION_TYPE: LOCAL,
        }
        assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_not_adax_device(hass: HomeAssistant) -> None:
    """Test DHCP discovery aborts if TLS check fails."""
    with patch(
        "homeassistant.components.adax.config_flow.is_adax_tls_device",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY_INFO,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "not_adax_device"


async def test_dhcp_discovery_already_configured_updates_ip(
    hass: HomeAssistant,
) -> None:
    """Test DHCP updates IP address if device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DHCP_UNIQUE_ID,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_TOKEN: "existing_token",
            CONF_UNIQUE_ID: TEST_DHCP_UNIQUE_ID,
            CONNECTION_TYPE: LOCAL,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "192.168.1.9"


@pytest.mark.parametrize(
    ("get_status_side_effect", "get_status_return_value", "expected_error"),
    [
        (aiohttp.ClientError, None, "cannot_connect"),
        (TimeoutError, None, "cannot_connect"),
        (RuntimeError("Unexpected error"), None, "unknown"),
        (None, {}, "cannot_connect"),
        (None, None, "cannot_connect"),
    ],
)
async def test_dhcp_confirm_connection_errors(
    hass: HomeAssistant,
    get_status_side_effect: Any,
    get_status_return_value: Any,
    expected_error: str,
) -> None:
    """Test connection and unknown errors during DHCP token confirmation and recovery."""
    with patch(
        "homeassistant.components.adax.config_flow.is_adax_tls_device",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    with patch(
        "homeassistant.components.adax.config_flow.AdaxLocal.get_status",
        new_callable=AsyncMock,
        side_effect=get_status_side_effect,
        return_value=get_status_return_value,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: "any_token"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": expected_error}

    # Recover from the error by submitting valid data and creating entry
    with (
        patch(
            "homeassistant.components.adax.config_flow.AdaxLocal.get_status",
            new_callable=AsyncMock,
            return_value={"current_temperature": 21.5},
        ),
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={CONF_TOKEN: "valid_secret_token"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["result"].unique_id == TEST_DHCP_UNIQUE_ID


@pytest.mark.parametrize(
    ("common_name", "expected_result"),
    [
        ("ADAX DEVICE", True),
        ("SOME OTHER DEVICE", False),
    ],
)
async def test_is_adax_tls_device_common_name(
    common_name: str, expected_result: bool
) -> None:
    """Test is_adax_tls_device verifies common name matching."""
    der_cert = _generate_test_der_cert(common_name)

    mock_ssl_obj = MagicMock()
    mock_ssl_obj.getpeercert.return_value = der_cert

    mock_writer = AsyncMock()
    mock_writer.get_extra_info = MagicMock(return_value=mock_ssl_obj)

    with patch("asyncio.open_connection", return_value=(AsyncMock(), mock_writer)):
        assert await is_adax_tls_device("192.168.1.9") is expected_result


async def test_is_adax_tls_device_no_cert() -> None:
    """Test is_adax_tls_device returns False if no cert is returned."""
    mock_ssl_obj = MagicMock()
    mock_ssl_obj.getpeercert.return_value = None

    mock_writer = AsyncMock()
    mock_writer.get_extra_info = MagicMock(return_value=mock_ssl_obj)

    with patch("asyncio.open_connection", return_value=(AsyncMock(), mock_writer)):
        assert await is_adax_tls_device("192.168.1.9") is False


async def test_is_adax_tls_device_connection_failure() -> None:
    """Test is_adax_tls_device handles socket connection errors gracefully."""
    with patch("asyncio.open_connection", side_effect=OSError):
        assert await is_adax_tls_device("192.168.1.9") is False
