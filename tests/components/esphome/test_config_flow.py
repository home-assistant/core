"""Test config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

from aioesphomeapi import (
    APIConnectionError,
    DeviceInfo,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    RequiresEncryptionAPIError,
    ResolveAPIError,
)
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import dhcp, zeroconf
from homeassistant.components.esphome import (
    CONF_DEVICE_NAME,
    CONF_NOISE_PSK,
    DOMAIN,
    DomainData,
    dashboard,
)
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import VALID_NOISE_PSK

from tests.common import MockConfigEntry

INVALID_NOISE_PSK = "lSYBYEjQI1bVL8s2Vask4YytGMj1f1epNtmoim2yuTM="


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch("homeassistant.components.esphome.async_setup_entry", return_value=True):
        yield


async def test_user_connection_works(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

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
        CONF_DEVICE_NAME: "test",
    }
    assert result["title"] == "test"
    assert result["result"].unique_id == "11:22:33:44:55:aa"

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1
    assert mock_client.host == "127.0.0.1"
    assert mock_client.port == 80
    assert mock_client.password == ""
    assert mock_client.noise_psk is None


async def test_user_connection_updates_host(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test setup up the same name updates the host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 80},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "127.0.0.1"


async def test_user_resolve_error(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
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


async def test_user_connection_error(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
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


async def test_user_with_password(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test user step with password."""
    mock_client.device_info.return_value = DeviceInfo(uses_password=True, name="test")

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
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.password == "password1"


async def test_user_invalid_password(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test user step with invalid password."""
    mock_client.device_info.return_value = DeviceInfo(uses_password=True, name="test")

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


async def test_login_connection_error(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test user step with connection error on login attempt."""
    mock_client.device_info.return_value = DeviceInfo(uses_password=True, name="test")

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


async def test_discovery_initiation(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test discovery importing works."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test.local.",
        name="mock_name",
        port=6053,
        properties={
            "mac": "1122334455aa",
        },
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"][CONF_HOST] == "192.168.43.183"
    assert result["data"][CONF_PORT] == 6053

    assert result["result"]
    assert result["result"].unique_id == "11:22:33:44:55:aa"


async def test_discovery_no_mac(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test discovery aborted if old ESPHome without mac in zeroconf."""
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
    assert flow["type"] == FlowResultType.ABORT
    assert flow["reason"] == "mdns_missing_mac"


async def test_discovery_already_configured(hass: HomeAssistant, mock_client) -> None:
    """Test discovery aborts if already configured via hostname."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test8266.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )

    entry.add_to_hass(hass)

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"mac": "1122334455aa"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_duplicate_data(hass: HomeAssistant, mock_client) -> None:
    """Test discovery aborts if same mDNS packet arrives."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test.local.",
        name="mock_name",
        port=6053,
        properties={"address": "test.local", "mac": "1122334455aa"},
        type="mock_type",
    )

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


async def test_discovery_updates_unique_id(hass: HomeAssistant, mock_client) -> None:
    """Test a duplicate discovery host aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )

    entry.add_to_hass(hass)

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"address": "test8266.local", "mac": "1122334455aa"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "11:22:33:44:55:aa"


async def test_user_requires_psk(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
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


async def test_encryption_key_valid_psk(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test encryption key step with valid key."""

    mock_client.device_info.side_effect = RequiresEncryptionAPIError

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "encryption_key"

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(uses_password=False, name="test")
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


async def test_encryption_key_invalid_psk(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
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


async def test_reauth_initiation(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
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


async def test_reauth_confirm_valid(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
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

    mock_client.device_info.return_value = DeviceInfo(uses_password=False, name="test")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


async def test_reauth_fixed_via_dashboard(
    hass: HomeAssistant, mock_client, mock_zeroconf: None, mock_dashboard
) -> None:
    """Test reauth fixed automatically via dashboard."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
    )
    entry.add_to_hass(hass)

    mock_client.device_info.return_value = DeviceInfo(uses_password=False, name="test")

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.dashboard.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        result = await hass.config_entries.flow.async_init(
            "esphome",
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
            },
        )

    assert result["type"] == FlowResultType.ABORT, result
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK

    assert len(mock_get_encryption_key.mock_calls) == 1


async def test_reauth_fixed_via_dashboard_add_encryption_remove_password(
    hass: HomeAssistant,
    mock_client,
    mock_zeroconf: None,
    mock_dashboard,
    mock_config_entry,
) -> None:
    """Test reauth fixed automatically via dashboard with password removed."""
    mock_client.device_info.side_effect = (
        InvalidAuthAPIError,
        DeviceInfo(uses_password=False, name="test"),
    )

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.dashboard.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        result = await hass.config_entries.flow.async_init(
            "esphome",
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
                "unique_id": mock_config_entry.unique_id,
            },
        )

    assert result["type"] == FlowResultType.ABORT, result
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK
    assert mock_config_entry.data[CONF_PASSWORD] == ""

    assert len(mock_get_encryption_key.mock_calls) == 1


async def test_reauth_fixed_via_remove_password(
    hass: HomeAssistant,
    mock_client,
    mock_config_entry,
    mock_dashboard,
) -> None:
    """Test reauth fixed automatically by seeing password removed."""
    mock_client.device_info.return_value = DeviceInfo(uses_password=False, name="test")

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
            "unique_id": mock_config_entry.unique_id,
        },
    )

    assert result["type"] == FlowResultType.ABORT, result
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == ""


async def test_reauth_fixed_via_dashboard_at_confirm(
    hass: HomeAssistant, mock_client, mock_zeroconf: None, mock_dashboard
) -> None:
    """Test reauth fixed automatically via dashboard at confirm step."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
    )
    entry.add_to_hass(hass)

    mock_client.device_info.return_value = DeviceInfo(uses_password=False, name="test")

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )

    assert result["type"] == FlowResultType.FORM, result
    assert result["step_id"] == "reauth_confirm"

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.dashboard.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        # We just fetch the form
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.ABORT, result
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK

    assert len(mock_get_encryption_key.mock_calls) == 1


async def test_reauth_confirm_invalid(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
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

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(uses_password=False, name="test")
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


async def test_reauth_confirm_invalid_with_unique_id(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test reauth initiation with invalid PSK."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="test",
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

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(uses_password=False, name="test")
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


async def test_discovery_dhcp_updates_host(hass: HomeAssistant, mock_client) -> None:
    """Test dhcp discovery updates host and aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    service_info = dhcp.DhcpServiceInfo(
        ip="192.168.43.184",
        hostname="test8266",
        macaddress="1122334455aa",
    )
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == "192.168.43.184"


async def test_discovery_dhcp_no_changes(hass: HomeAssistant, mock_client) -> None:
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

    assert entry.data[CONF_HOST] == "192.168.43.183"


async def test_discovery_hassio(hass: HomeAssistant, mock_dashboard) -> None:
    """Test dashboard discovery."""
    result = await hass.config_entries.flow.async_init(
        "esphome",
        data=HassioServiceInfo(
            config={
                "host": "mock-esphome",
                "port": 6052,
            },
            name="ESPHome",
            slug="mock-slug",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "service_received"

    dash = dashboard.async_get_dashboard(hass)
    assert dash is not None
    assert dash.addon_slug == "mock-slug"


async def test_zeroconf_encryption_key_via_dashboard(
    hass: HomeAssistant, mock_client, mock_zeroconf: None, mock_dashboard
) -> None:
    """Test encryption key retrieved from dashboard."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={
            "mac": "1122334455aa",
        },
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert flow["type"] == FlowResultType.FORM
    assert flow["step_id"] == "discovery_confirm"

    mock_dashboard["configured"].append(
        {
            "name": "test8266",
            "configuration": "test8266.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    mock_client.device_info.side_effect = [
        RequiresEncryptionAPIError,
        DeviceInfo(
            uses_password=False,
            name="test8266",
            mac_address="11:22:33:44:55:aa",
        ),
    ]

    with patch(
        "homeassistant.components.esphome.dashboard.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input={}
        )

    assert len(mock_get_encryption_key.mock_calls) == 1

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test8266"
    assert result["data"][CONF_HOST] == "192.168.43.183"
    assert result["data"][CONF_PORT] == 6053
    assert result["data"][CONF_NOISE_PSK] == VALID_NOISE_PSK

    assert result["result"]
    assert result["result"].unique_id == "11:22:33:44:55:aa"

    assert mock_client.noise_psk == VALID_NOISE_PSK


async def test_zeroconf_no_encryption_key_via_dashboard(
    hass: HomeAssistant, mock_client, mock_zeroconf: None, mock_dashboard
) -> None:
    """Test encryption key not retrieved from dashboard."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={
            "mac": "1122334455aa",
        },
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        "esphome", context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert flow["type"] == FlowResultType.FORM
    assert flow["step_id"] == "discovery_confirm"

    await dashboard.async_get_dashboard(hass).async_refresh()

    mock_client.device_info.side_effect = RequiresEncryptionAPIError

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
