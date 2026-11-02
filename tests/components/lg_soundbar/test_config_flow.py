"""Test the lg_soundbar config flow."""

from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock

from aiotemescal import TemescalConnectionError, TemescalTimeoutError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.lg_soundbar.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import set_answers

USER_INPUT = {CONF_HOST: "1.1.1.1"}

ZEROCONF_UUID = "6ae736a7-4781-42fe-b096-47279619fb9d"


def zeroconf_info(host: str = "1.1.1.1") -> ZeroconfServiceInfo:
    """Return the announcement of a soundbar."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        hostname="audiocast.local.",
        name=f"LG_SMART_AUDIO-{ZEROCONF_UUID}._lg-smart-device._tcp.local.",
        port=DEFAULT_PORT,
        type="_lg-smart-device._tcp.local.",
        properties={"PROTO_VER": "1.0", "UUID": ZEROCONF_UUID, "ipv4": host},
    )


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "answers",
    [
        pytest.param(
            {
                "SPK_LIST_VIEW_INFO": {"s_user_name": "name"},
                "MAC_INFO_DEV": {"s_uuid": "uuid"},
            },
            id="uuid_in_mac_info",
        ),
        pytest.param(
            {
                "SPK_LIST_VIEW_INFO": {"s_user_name": "name"},
                "PRODUCT_INFO": {"s_uuid": "uuid"},
            },
            id="no_mac_info",
        ),
        pytest.param(
            {
                "SPK_LIST_VIEW_INFO": {"s_user_name": "name"},
                "MAC_INFO_DEV": {},
                "PRODUCT_INFO": {"s_uuid": "uuid"},
            },
            id="uuid_missing_from_mac_info",
        ),
    ],
)
async def test_user_flow(
    hass: HomeAssistant, mock_client: AsyncMock, answers: dict[str, Any]
) -> None:
    """Test creating an entry, wherever the device reports its uuid."""
    set_answers(mock_client, answers)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "name"
    assert result["result"].unique_id == "uuid"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_PORT}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_without_uuid(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test creating an entry for a device that never reports its uuid."""
    set_answers(mock_client, {"SPK_LIST_VIEW_INFO": {"s_user_name": "name"}})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "name"
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "answers", "error"),
    [
        pytest.param(
            TemescalConnectionError, {}, "cannot_connect", id="cannot_connect"
        ),
        pytest.param(TemescalTimeoutError, {}, "cannot_connect", id="connect_timeout"),
        pytest.param(
            None, {"MAC_INFO_DEV": {"s_uuid": "uuid"}}, "no_data", id="no_name"
        ),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    side_effect: type[Exception] | None,
    answers: dict[str, Any],
    error: str,
) -> None:
    """Test errors are reported and the flow can recover from them."""
    mock_client.__aenter__.side_effect = side_effect
    original_request = mock_client.request.side_effect
    set_answers(mock_client, answers)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.__aenter__.side_effect = None
    mock_client.request.side_effect = original_request

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("unique_id", "answers"),
    [
        pytest.param(
            "uuid",
            {
                "SPK_LIST_VIEW_INFO": {"s_user_name": "name"},
                "MAC_INFO_DEV": {"s_uuid": "uuid"},
            },
            id="same_uuid",
        ),
        pytest.param(
            None,
            {"SPK_LIST_VIEW_INFO": {"s_user_name": "name"}},
            id="same_host_without_uuid",
        ),
    ],
)
async def test_already_configured(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    unique_id: str | None,
    answers: dict[str, Any],
) -> None:
    """Test a device is not added twice."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_PORT},
        unique_id=unique_id,
    ).add_to_hass(hass)
    set_answers(mock_client, answers)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test setting up an announced soundbar, identified by its reported uuid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=zeroconf_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "name"
    assert result["result"].unique_id == "uuid"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_PORT}


@pytest.mark.usefixtures("mock_client")
async def test_zeroconf_updates_host(hass: HomeAssistant) -> None:
    """Test a configured soundbar announced at a new address is followed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_PORT},
        unique_id="uuid",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=zeroconf_info("2.2.2.2")
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "2.2.2.2"


@pytest.mark.parametrize(
    "unique_id",
    [
        pytest.param("uuid", id="with_uuid"),
        pytest.param(None, id="without_uuid"),
    ],
)
async def test_zeroconf_configured_host(
    hass: HomeAssistant, mock_client: AsyncMock, unique_id: str | None
) -> None:
    """Test an announcement at a configured address leaves the entry alone."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_PORT},
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=zeroconf_info()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == unique_id
    # Rediscovering a configured soundbar does not connect to it
    mock_client.__aenter__.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "answers", "reason"),
    [
        pytest.param(
            TemescalConnectionError, {}, "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            None, {"MAC_INFO_DEV": {"s_uuid": "uuid"}}, "no_data", id="no_name"
        ),
        pytest.param(
            None,
            {"SPK_LIST_VIEW_INFO": {"s_user_name": "name"}},
            "not_supported",
            id="no_uuid",
        ),
    ],
)
async def test_zeroconf_abort(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    side_effect: type[Exception] | None,
    answers: dict[str, Any],
    reason: str,
) -> None:
    """Test announcements that cannot be set up."""
    mock_client.__aenter__.side_effect = side_effect
    set_answers(mock_client, answers)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=zeroconf_info()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
