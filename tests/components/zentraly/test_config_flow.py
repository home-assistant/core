"""Tests for the Zentraly config flow."""

from ipaddress import ip_address
from unittest.mock import MagicMock, patch

import pytest
from zentraly import ZentralyAuthenticationError, ZentralyConnectionError

from homeassistant import config_entries
from homeassistant.components.zentraly.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import DEVICE_ID, HOST, PASSWORD, PORT

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_api")
NEW_HOST = "192.168.1.43"
NEW_PORT = 12346


def _zeroconf_info(
    host: str = HOST, port: int = PORT, device_id: str = DEVICE_ID
) -> ZeroconfServiceInfo:
    """Return mock Zentraly Zeroconf discovery information."""
    address = ip_address(host)
    return ZeroconfServiceInfo(
        ip_address=address,
        ip_addresses=[address],
        hostname=f"{device_id}.local.",
        name=f"{device_id}._zentraly._tcp.local.",
        port=port,
        properties={},
        type="_zentraly._tcp.local.",
    )


async def test_zeroconf_auth_success(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Discover, authenticate and create a uniquely identified entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_ID
    assert result["result"].unique_id == DEVICE_ID
    assert result["data"] == {
        "host": HOST,
        "port": PORT,
        "device_id": DEVICE_ID,
        "password": PASSWORD,
        "mac": mock_api.async_validate_password.return_value,
    }
    mock_setup_entry.assert_awaited_once()


@pytest.mark.parametrize(
    "device_id",
    [
        "UNKNOWN",
        "ZTTWZ0100000001",
        "ZTBIN0100000001",
        "ZTREA0100000001",
        "ZTEIM0100000001",
        "ZTIKD0100000001",
        "ZTIKS0100000001",
    ],
)
async def test_zeroconf_unsupported_device(hass: HomeAssistant, device_id: str) -> None:
    """Ignore devices outside the initial thermostat scope."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(device_id=device_id),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_device"


@pytest.mark.parametrize(
    ("error", "key"),
    [
        pytest.param(ZentralyAuthenticationError, "invalid_auth", id="authentication"),
        pytest.param(ZentralyConnectionError, "cannot_connect", id="connection"),
    ],
)
async def test_auth_recovery(
    hass: HomeAssistant, mock_api: MagicMock, error: type[Exception], key: str
) -> None:
    """A failed validation remains recoverable without restarting discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )
    mock_api.async_validate_password.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "wrong-password"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": key}
    mock_api.async_validate_password.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ID
    assert result["data"][CONF_PASSWORD] == PASSWORD


@pytest.mark.parametrize(
    ("host", "port"),
    [
        pytest.param(NEW_HOST, NEW_PORT, id="changed"),
        pytest.param(HOST, PORT, id="unchanged"),
    ],
)
async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, host: str, port: int
) -> None:
    """Rediscovery updates only the network endpoint of an existing entry."""
    data = dict(mock_config_entry.data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(host=host, port=port),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {**data, CONF_HOST: host, CONF_PORT: port}


async def test_user_setup_without_discoveries(hass: HomeAssistant) -> None:
    """Explain that a thermostat must be discovered before setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "zeroconf_only"


@pytest.mark.parametrize(
    ("host", "port", "reload_count"),
    [
        pytest.param(NEW_HOST, PORT, 1, id="new-host"),
        pytest.param(HOST, NEW_PORT, 1, id="new-port"),
        pytest.param(HOST, PORT, 0, id="unchanged"),
    ],
)
async def test_loaded_entry_rediscovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    host: str,
    port: int,
    reload_count: int,
) -> None:
    """Reload a configured thermostat only when its network endpoint changes."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_info(host=host, port=port),
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == host
    assert mock_config_entry.data[CONF_PORT] == port
    assert reload.await_count == reload_count
