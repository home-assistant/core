"""Tests for the Music Player Daemon config flow."""

from dataclasses import replace
from ipaddress import ip_address
from socket import gaierror
from typing import Any
from unittest.mock import AsyncMock

import mpd
import pytest

from homeassistant.components.mpd.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

INVALID_PASSWORD_ERROR = mpd.CommandError("[3@0] {password} incorrect password")

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.0.1"),
    ip_addresses=[ip_address("192.168.0.1"), ip_address("2001:db8::1")],
    port=6600,
    hostname="mpd-server.local.",
    type="_mpd._tcp.local.",
    name="mpd-server._mpd._tcp.local.",
    properties={},
)


@pytest.mark.parametrize(
    ("user_input", "expected_data"),
    [
        pytest.param(
            {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
            {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
            id="with_password",
        ),
        pytest.param(
            {CONF_HOST: "192.168.0.1", CONF_PORT: 6600},
            {CONF_HOST: "192.168.0.1", CONF_PORT: 6600},
            id="without_password",
        ),
        pytest.param(
            {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: ""},
            {CONF_HOST: "192.168.0.1", CONF_PORT: 6600},
            id="empty_password",
        ),
    ],
)
async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mpd_client: AsyncMock,
    user_input: dict[str, str | int],
    expected_data: dict[str, str | int],
) -> None:
    """Test the happy flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Music Player Daemon"
    assert result["data"] == expected_data
    # An empty field is not a password, so the server is never asked to check it.
    assert mock_mpd_client.password.called is (CONF_PASSWORD in expected_data)
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TimeoutError, "cannot_connect"),
        (gaierror, "cannot_connect"),
        (mpd.ConnectionError, "cannot_connect"),
        (mpd.ProtocolError, "cannot_connect"),
        (OSError, "cannot_connect"),
        pytest.param(
            INVALID_PASSWORD_ERROR, "invalid_auth", id="CommandError-invalid_auth"
        ),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_errors(
    hass: HomeAssistant, mock_mpd_client: AsyncMock, exception: Exception, error: str
) -> None:
    """Test we handle errors correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    mock_mpd_client.password.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    # The connection must be released even when validation raises.
    assert mock_mpd_client.disconnect.called

    mock_mpd_client.password.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_existing_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if an entry already exists."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("user_input", "expected_data"),
    [
        pytest.param(
            {CONF_PASSWORD: "test123"},
            {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
            id="with_password",
        ),
        pytest.param(
            {},
            {CONF_HOST: "192.168.0.1", CONF_PORT: 6600},
            id="without_password",
        ),
        pytest.param(
            {CONF_PASSWORD: ""},
            {CONF_HOST: "192.168.0.1", CONF_PORT: 6600},
            id="empty_password",
        ),
    ],
)
async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mpd_client: AsyncMock,
    user_input: dict[str, str],
    expected_data: dict[str, str | int],
) -> None:
    """Test the zeroconf discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "mpd-server"
    assert result["data"] == expected_data
    # A read proves the credentials grant access, not just that MPD greeted us.
    assert mock_mpd_client.status.called
    # The hostname and port deduplicate flows only; they are not an identity.
    assert result["result"].unique_id is None
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_mpd_client", "mock_setup_entry")
async def test_zeroconf_flow_default_port(hass: HomeAssistant) -> None:
    """Test the zeroconf flow falls back to the default port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(ZEROCONF_DISCOVERY, port=None),
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["data"] == {CONF_HOST: "192.168.0.1", CONF_PORT: 6600}


@pytest.mark.parametrize(
    "configured_host",
    [
        pytest.param("192.168.0.1", id="ip_address"),
        pytest.param("2001:db8::1", id="other_advertised_address"),
        pytest.param("2001:0db8:0000:0000:0000:0000:0000:0001", id="expanded_address"),
        pytest.param("mpd-server.local", id="fqdn"),
        pytest.param("mpd-server.local.", id="canonical_fqdn"),
        pytest.param("mpd-server", id="hostname"),
        pytest.param("MPD-SERVER.LOCAL", id="upper_case_fqdn"),
    ],
)
@pytest.mark.usefixtures("mock_mpd_client")
async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant, configured_host: str
) -> None:
    """Test the zeroconf flow aborts for an already configured server."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: configured_host, CONF_PORT: 6600},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_mpd_client", "mock_setup_entry")
async def test_zeroconf_flow_second_server(hass: HomeAssistant) -> None:
    """Test a second server is still offered when another one is configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.0.1", CONF_PORT: 6600},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(
            ZEROCONF_DISCOVERY,
            ip_address=ip_address("192.168.0.9"),
            ip_addresses=[ip_address("192.168.0.9")],
            hostname="other-mpd.local.",
            name="other-mpd._mpd._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.0.9", CONF_PORT: 6600}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


@pytest.mark.parametrize(
    "reannouncement",
    [
        pytest.param(
            {
                "ip_address": ip_address("2001:db8::1"),
                "ip_addresses": [ip_address("2001:db8::1"), ip_address("192.168.0.1")],
            },
            id="another_address",
        ),
        pytest.param({"hostname": "MPD-SERVER.LOCAL."}, id="another_hostname_casing"),
    ],
)
@pytest.mark.usefixtures("mock_mpd_client")
async def test_zeroconf_flow_already_in_progress(
    hass: HomeAssistant, reannouncement: dict[str, Any]
) -> None:
    """Test a reannouncement of one server does not open a second flow."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(ZEROCONF_DISCOVERY, **reannouncement),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_mpd_client")
async def test_zeroconf_flow_already_in_progress_after_restart(
    hass: HomeAssistant,
) -> None:
    """Test a restart renaming the DNS-SD instance does not open a flow.

    MPD appends its pid to the instance name, so the name differs on every
    announcement made by a new process.
    """
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(
            ZEROCONF_DISCOVERY,
            name="Music Player @ mpd-server[4242]._mpd._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 1


async def test_zeroconf_flow_cannot_connect(
    hass: HomeAssistant, mock_mpd_client: AsyncMock
) -> None:
    """Test the zeroconf flow aborts when the server cannot be reached."""
    mock_mpd_client.connect.side_effect = mpd.ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_password_protected(
    hass: HomeAssistant, mock_mpd_client: AsyncMock
) -> None:
    """Test a server refusing the unauthenticated probe still offers the form."""
    mock_mpd_client.status.side_effect = INVALID_PASSWORD_ERROR

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    mock_mpd_client.status.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "test123"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_mpd_client", "mock_setup_entry")
async def test_zeroconf_flow_configured_while_confirming(
    hass: HomeAssistant,
) -> None:
    """Test the server being configured while the confirm form is open aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    assert result["type"] is FlowResultType.FORM

    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.0.1", CONF_PORT: 6600},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_invalid_auth(
    hass: HomeAssistant, mock_mpd_client: AsyncMock
) -> None:
    """Test a wrong password re-shows the confirm form instead of aborting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    mock_mpd_client.password.side_effect = INVALID_PASSWORD_ERROR

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_mpd_client.password.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "test123"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
