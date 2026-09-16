"""Tests for the Zentraly config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

import pytest
from zentraly import ZentralyAuthenticationError, ZentralyConnectionError

from homeassistant import config_entries
from homeassistant.components.zentraly.const import DOMAIN
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

DEVICE_ID = "ZTTIN0100000631"
HOST = "192.168.1.42"
NEW_HOST = "192.168.1.43"
PORT = 12345
NEW_PORT = 12346
MAC = "dcda0c58c8d8"
PASSWORD = "test-password"


def _zeroconf_info(
    host: str = HOST,
    port: int = PORT,
    device_id: str = DEVICE_ID,
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


def _parent_entry(
    *,
    state: config_entries.ConfigEntryState = config_entries.ConfigEntryState.LOADED,
) -> MockConfigEntry:
    """Return a mock Zentraly parent config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ID,
        state=state,
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_PASSWORD: PASSWORD,
            CONF_MAC: MAC,
        },
    )


@pytest.mark.parametrize(
    ("device_id", "mac"),
    [
        (DEVICE_ID, MAC),
    ],
)
async def test_zeroconf_auth_success(
    hass: HomeAssistant,
    device_id: str,
    mac: str,
) -> None:
    """Test successful Zeroconf discovery and authentication."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(
            device_id=device_id,
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    with patch(
        "homeassistant.components.zentraly.config_flow."
        "ZentralyApi.async_validate_password",
        new_callable=AsyncMock,
        return_value=mac,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device_id

    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_DEVICE_ID: device_id,
        CONF_PASSWORD: PASSWORD,
        CONF_MAC: mac,
    }


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
async def test_zeroconf_unsupported_device(
    hass: HomeAssistant,
    device_id: str,
) -> None:
    """Test unsupported Zeroconf devices are ignored."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(
            device_id=device_id,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_device"


async def test_invalid_auth_recovery(
    hass: HomeAssistant,
) -> None:
    """Test recovery after invalid authentication."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )

    with patch(
        "homeassistant.components.zentraly.config_flow."
        "ZentralyApi.async_validate_password",
        new_callable=AsyncMock,
        side_effect=ZentralyAuthenticationError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "wrong-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.zentraly.config_flow."
        "ZentralyApi.async_validate_password",
        new_callable=AsyncMock,
        return_value=MAC,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == MAC
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_cannot_connect_recovery(
    hass: HomeAssistant,
) -> None:
    """Test recovery after a connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )

    with patch(
        "homeassistant.components.zentraly.config_flow."
        "ZentralyApi.async_validate_password",
        new_callable=AsyncMock,
        side_effect=ZentralyConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.zentraly.config_flow."
        "ZentralyApi.async_validate_password",
        new_callable=AsyncMock,
        return_value=MAC,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_already_configured_updates_address(
    hass: HomeAssistant,
) -> None:
    """Test rediscovery updates host and port of an existing entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ID,
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_PASSWORD: PASSWORD,
            CONF_MAC: MAC,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(
            host=NEW_HOST,
            port=NEW_PORT,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == NEW_HOST
    assert entry.data[CONF_PORT] == NEW_PORT
    assert entry.data[CONF_DEVICE_ID] == DEVICE_ID
    assert entry.data[CONF_MAC] == MAC
    assert entry.data[CONF_PASSWORD] == PASSWORD


async def test_zeroconf_already_configured_same_address(
    hass: HomeAssistant,
) -> None:
    """Test rediscovery keeps an unchanged host and port."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ID,
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_PASSWORD: PASSWORD,
            CONF_MAC: MAC,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == HOST
    assert entry.data[CONF_PORT] == PORT
    assert entry.data[CONF_DEVICE_ID] == DEVICE_ID
    assert entry.data[CONF_MAC] == MAC
    assert entry.data[CONF_PASSWORD] == PASSWORD


async def test_user_setup_without_discoveries(
    hass: HomeAssistant,
) -> None:
    """Explain when there are no configured parent devices."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "zeroconf_only"
