"""Tests for the LANBON config flow."""

from collections.abc import Generator
from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from aiolanbon import LanbonAuthError, LanbonConnectionError
import pytest

from homeassistant.components.lanbon.config_flow import ApiDisabled
from homeassistant.components.lanbon.const import CONF_GATEWAY_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import GATEWAY_ID, HOST, PORT, TOKEN, gateway_info

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Prevent actual setup during config flow tests."""
    with patch(
        "homeassistant.components.lanbon.async_setup_entry",
        return_value=True,
    ):
        yield


def _discovery(**properties: str) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ip_address(HOST),
        ip_addresses=[ip_address(HOST)],
        port=PORT,
        hostname="lanbon.local.",
        type="_lanbon._tcp.local.",
        name="L10-4G._lanbon._tcp.local.",
        properties=properties,
    )


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test user config flow success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema_keys = [
        str(getattr(key, "schema", key)) for key in result["data_schema"].schema
    ]
    joined = " ".join(schema_keys).lower()
    assert "host" in joined and "token" in joined
    assert "enable" not in joined

    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonClient.get_info",
        new=AsyncMock(return_value=gateway_info()),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "L10-4G"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["data"][CONF_TOKEN] == TOKEN
    assert result["data"][CONF_GATEWAY_ID] == GATEWAY_ID
    assert "sw_type" not in result["data"]


async def test_user_flow_recovers_after_errors(hass: HomeAssistant) -> None:
    """Test user flow recovers after auth, disabled API, and connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonClient.get_info",
        new=AsyncMock(side_effect=LanbonAuthError("bad")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: "bad"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"

    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonClient.get_info",
        new=AsyncMock(return_value=gateway_info(api_enabled=False)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "api_disabled"

    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonClient.get_info",
        new=AsyncMock(side_effect=LanbonConnectionError("down")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonClient.get_info",
        new=AsyncMock(return_value=gateway_info()),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_GATEWAY_ID] == GATEWAY_ID


async def test_user_api_disabled_raises(hass: HomeAssistant) -> None:
    """Test Open Integration off is ApiDisabled, not a connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lanbon.config_flow._validate",
        new=AsyncMock(side_effect=ApiDisabled),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
    assert result["errors"]["base"] == "api_disabled"


async def test_zeroconf_flow_ignores_txt_token(hass: HomeAssistant) -> None:
    """Discovery must not use a token from TXT; user pastes it."""
    discovery = _discovery(
        id=GATEWAY_ID,
        model="L10-4G",
        token="from-txt-must-not-be-used",
        path="/api/v1",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonClient.get_info",
        new=AsyncMock(return_value=gateway_info()),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TOKEN}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == TOKEN
    assert result["data"][CONF_TOKEN] != "from-txt-must-not-be-used"
    assert result["data"][CONF_GATEWAY_ID] == GATEWAY_ID


async def test_abort_already_configured(hass: HomeAssistant) -> None:
    """Test abort when unique_id exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GATEWAY_ID,
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonClient.get_info",
        new=AsyncMock(return_value=gateway_info()),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.0.0.2", CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_updates_host_when_already_configured(
    hass: HomeAssistant,
) -> None:
    """Zeroconf may refresh host/port for an existing unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GATEWAY_ID,
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
    )
    entry.add_to_hass(hass)

    discovery = ZeroconfServiceInfo(
        ip_address=ip_address("10.0.0.9"),
        ip_addresses=[ip_address("10.0.0.9")],
        port=9000,
        hostname="lanbon.local.",
        type="_lanbon._tcp.local.",
        name="L10-4G._lanbon._tcp.local.",
        properties={"id": GATEWAY_ID, "model": "L10-4G"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "10.0.0.9"
    assert entry.data[CONF_PORT] == 9000
