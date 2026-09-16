"""Tests for the Habitron config flow."""

from ipaddress import IPv4Address
import socket
from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import (
    HabitronConnectionError,
    HabitronError,
    HabitronProtocolError,
    HabitronTimeoutError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.habitron.config_flow import (
    CannotConnect,
    ConfigFlow,
    HostNotFound,
    _async_hub_mac,
    validate_input,
)
from homeassistant.components.habitron.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import (
    MOCK_CONFIG_DATA,
    MOCK_HOST,
    MOCK_HOST_HOSTNAME,
    MOCK_MAC,
    MOCK_NAME,
    MOCK_SERIAL,
    MOCK_UDN,
    MOCK_UID,
)

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """The manual user flow creates an entry when the hub responds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == MOCK_CONFIG_DATA


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A failing connect probe surfaces ``cannot_connect``."""
    mock_habitron_client.return_value = (False, "")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_recovers_after_an_error(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """The form stays usable after a failure: fix the address, get an entry.

    Showing the error is only half of it -- what matters to the user is that the
    same flow still leads somewhere once the hub answers, without starting over.
    """
    mock_habitron_client.return_value = (False, "")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_habitron_client.return_value = (True, MOCK_NAME)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == MOCK_CONFIG_DATA


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An identical config aborts with ``already_configured``.

    Both the existing entry and the flow key on the hub's MAC, so the plain
    unique-id check is what fires here.
    """
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_update_keeps_the_local_sentinel(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A hub stored as ``local`` is not rewritten to the discovered IP.

    The sentinel resolves to whatever address this machine currently has;
    replacing it with the IP seen at discovery time would leave setup pointing
    at a stale address as soon as that changes.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data={CONF_HOST: "local"},
    )
    entry.add_to_hass(hass)

    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )
    with patch(
        "homeassistant.components.habitron.config_flow.network."
        "async_get_enabled_source_ips",
        new=AsyncMock(return_value=[IPv4Address(MOCK_HOST)]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_HOST] == "local"


async def test_user_step_updates_the_stored_host_of_a_known_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """Re-adding a known hub at a new address moves the entry to it.

    The MAC identifies the same hub, so aborting without the update would leave
    the entry pointing at the address it no longer answers on.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data={CONF_HOST: "192.168.1.99"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": MOCK_SERIAL}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_HOST] == MOCK_HOST


async def test_ssdp_adopts_an_entry_keyed_by_the_hub_mac(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A hub added by the custom integration is not offered a second time.

    Those entries are keyed by the hub's MAC -- and so is everything this flow
    creates, so the plain unique-id check recognises them, even after the
    address changed and no host matches any more.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="d83addbae72e",
        data={CONF_HOST: "192.168.1.99"},
    )
    entry.add_to_hass(hass)

    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )
    with patch(
        "homeassistant.components.habitron.config_flow._async_hub_mac",
        new=AsyncMock(return_value="d83addbae72e"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # The id it already had *is* the identity, so only the address moves.
    assert entry.unique_id == "d83addbae72e"
    assert entry.data[CONF_HOST] == MOCK_HOST


def _smhub_info(lan_mac: str | None) -> dict:
    """A complete ``GET_SMHUB_INFO`` answer carrying ``lan_mac``.

    Complete on purpose: the client validates the payload before returning it,
    so a partial one never reaches the code under test.
    """
    return {
        "hardware": {
            "platform": {"type": "Raspberry Pi 4 Model B"},
            "network": {"ip": MOCK_HOST, "host": "smarthub", "lan mac": lan_mac},
        },
        "software": {"version": "5.1.0"},
    }


@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        ("D8:3A:DD:BA:E7:2E", "d83addbae72e"),
        ("d8-3a-dd-ba-e7-2e", "d83addbae72e"),
        ("", None),
        # A hub with no LAN interface reports the key as null. Stringifying
        # that would key every such hub by the literal "none".
        (None, None),
    ],
)
async def test_hub_mac_is_normalised(
    reported: str | None, expected: str | None
) -> None:
    """The probed MAC is comparable regardless of separators and casing.

    Entries from the custom integration store it colon-stripped and lower case;
    the hub itself reports whichever notation its firmware happens to use.
    """
    client = AsyncMock()
    client.get_smhub_info = AsyncMock(return_value=_smhub_info(reported))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "homeassistant.components.habitron.config_flow.HabitronClient",
        return_value=client,
    ):
        assert await _async_hub_mac(MOCK_HOST) == expected


async def test_hub_mac_unreachable_raises_cannot_connect() -> None:
    """An unreachable hub is a connection problem, not a missing MAC.

    The two need different answers: telling someone to update the hub software
    helps nobody whose address is simply wrong.
    """
    with (
        patch(
            "homeassistant.components.habitron.config_flow.HabitronClient",
            side_effect=OSError("no route"),
        ),
        pytest.raises(CannotConnect),
    ):
        await _async_hub_mac(MOCK_HOST)


@pytest.mark.parametrize(
    "reported",
    [None, "", "192.168.1.50", "not-a-mac"],
    ids=["null", "empty", "an IP", "junk"],
)
async def test_hub_mac_without_a_usable_address_is_none(reported: str | None) -> None:
    """Only a real address becomes an identity.

    A hub that answers but sends something else -- a null ``lan mac``, or a
    value that is not an address at all -- must not have it turned into a
    unique_id that two machines could share.
    """
    client = MagicMock()
    client.get_smhub_info = AsyncMock(return_value=_smhub_info(reported))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "homeassistant.components.habitron.config_flow.HabitronClient",
        return_value=client,
    ):
        assert await _async_hub_mac(MOCK_HOST) is None


async def test_hub_mac_unreadable_answer_raises_cannot_connect() -> None:
    """A payload the client cannot read is a connection problem, not "no MAC".

    ``get_smhub_info`` validates the answer, so an incomplete one never reaches
    the identity check -- it arrives as a ``HabitronProtocolError``, and the
    flow must offer "cannot connect" rather than the "update your hub" path a
    missing MAC leads to.
    """
    client = MagicMock()
    client.get_smhub_info = AsyncMock(
        side_effect=HabitronProtocolError("SmartHub info: missing key")
    )
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with (
        patch(
            "homeassistant.components.habitron.config_flow.HabitronClient",
            return_value=client,
        ),
        pytest.raises(CannotConnect),
    ):
        await _async_hub_mac(MOCK_HOST)


@pytest.mark.parametrize(
    ("reported_mac", "expected_type"),
    [
        # The same hub, however it was reached before.
        ("d83addbae72e", FlowResultType.ABORT),
        # A different hub is a genuinely new device.
        ("001122334455", FlowResultType.CREATE_ENTRY),
        # No MAC, no identity: the form comes back with an error.
        (None, FlowResultType.FORM),
    ],
)
async def test_user_step_mac_match_normalises_and_falls_through(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    reported_mac: str | None,
    expected_type: FlowResultType,
) -> None:
    """The MAC comparison ignores notation and only matches the same hub."""
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="d83addbae72e",
        data={CONF_HOST: "192.168.1.99"},
    ).add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.habitron.config_flow.discover_smarthubs",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.habitron.config_flow._async_hub_mac",
            new=AsyncMock(return_value=reported_mac),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is expected_type


async def test_user_step_falls_back_to_the_hub_mac(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """Without a serial the MAC keys the entry, not the address.

    A host-based id changes with every DHCP lease, which is what lets the same
    hub be configured twice.
    """
    mock_hub_mac.return_value = "d83addbae72e"
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "d83addbae72e"


async def test_ssdp_falls_back_to_the_hub_mac(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """A hub advertising neither UDN nor serial is still keyed stably."""
    mock_hub_mac.return_value = "d83addbae72e"
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={},
    )
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["result"].unique_id == "d83addbae72e"


@pytest.mark.parametrize(
    "probed",
    [
        # No serial: the MAC becomes the unique id, so the entry matches on it.
        [],
        # A serial is advertised, so the derived id differs from the stored MAC
        # and only the MAC lookup can still recognise the hub.
        [{"ip": MOCK_HOST, "serial": MOCK_SERIAL}],
    ],
    ids=["no_serial", "serial_advertised"],
)
async def test_user_step_keeps_a_mac_keyed_entry_id(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_hub_mac: AsyncMock,
    probed: list[dict[str, str]],
) -> None:
    """Re-adding a MAC-keyed hub corrects its address, not its id.

    The MAC is the most stable identifier available here, so replacing it with
    a serial- or host-based id would undo exactly what it protects against.
    """
    mock_hub_mac.return_value = "d83addbae72e"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="d83addbae72e",
        data={CONF_HOST: "192.168.1.99"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=probed),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert entry.unique_id == "d83addbae72e"
    assert entry.data[CONF_HOST] == MOCK_HOST


async def test_user_step_probes_the_resolved_ip_for_the_local_sentinel(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """``local`` is resolved before the hub is dialled.

    It is our own sentinel, not a name any resolver knows, so probing it
    directly would fail -- and with it the stable-id fallback for a hub running
    on this very machine.
    """
    mock_hub_mac.return_value = "d83addbae72e"
    with (
        patch(
            "homeassistant.components.habitron.config_flow.discover_smarthubs",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.network.async_get_source_ip",
            new=AsyncMock(return_value=MOCK_HOST),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "local"}
        )
        await hass.async_block_till_done()

    mock_hub_mac.assert_awaited_with(MOCK_HOST)
    assert result["result"].unique_id == "d83addbae72e"


async def test_user_step_can_reconfigure_an_ignored_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A hub the user ignored can still be added by hand later.

    Core lets ``_abort_if_unique_id_configured`` pass for an ignored entry in a
    user flow -- that is how un-ignoring works. The extra host check must not
    abort behind its back, or the hub could never be configured again.
    """
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_SERIAL,
        source=config_entries.SOURCE_IGNORE,
        data={CONF_HOST: MOCK_HOST},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": MOCK_SERIAL}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_unignores_a_mac_keyed_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """An ignored hub keyed by its MAC can be added by hand again.

    Core lets a new entry replace an ignored one with the same unique id, so
    the flow adopts that MAC instead of aborting.
    """
    mock_hub_mac.return_value = "d83addbae72e"
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="d83addbae72e",
        source=config_entries.SOURCE_IGNORE,
        data={CONF_HOST: MOCK_HOST},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": MOCK_SERIAL}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "d83addbae72e"


async def test_ssdp_no_host(
    hass: HomeAssistant,
    setup_homeassistant: None,
) -> None:
    """SSDP without a hostname is aborted."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=None,
        upnp={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_host_in_ssdp"


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (HabitronTimeoutError("timeout"), "cannot_connect"),
        (ConnectionRefusedError("refused"), "cannot_connect"),
    ],
)
async def test_user_flow_exception_mapping(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    exception: Exception,
    expected: str,
) -> None:
    """Connection errors map to expected form errors."""
    mock_habitron_client.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_validate_input_local_loopback_rewrites_host(
    hass: HomeAssistant,
    mock_habitron_client: MagicMock,
) -> None:
    """A host equal to one of our own IPs is rewritten to ``local``."""

    data = {CONF_HOST: "192.168.1.10"}
    info = await validate_input(hass, data)
    assert data[CONF_HOST] == "local"
    assert info == {"title": MOCK_NAME}


async def test_validate_input_falls_back_to_host_when_hub_unnamed(
    hass: HomeAssistant,
) -> None:
    """A hub that answers the probe but reports no name gets a host title.

    ``test_connection`` returns ``(True, "")`` when the TCP probe succeeds but
    the metadata query is unanswered; the entry must not end up blank.
    """

    with (
        patch(
            "homeassistant.components.habitron.config_flow.network.async_get_source_ip",
            new=AsyncMock(return_value="10.0.0.5"),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.test_connection",
            new=AsyncMock(return_value=(True, "")),
        ),
    ):
        info = await validate_input(hass, {CONF_HOST: "192.168.1.77"})

    assert info == {"title": "192.168.1.77"}


async def test_validate_input_accepts_short_hostname(
    hass: HomeAssistant,
    mock_habitron_client: MagicMock,
) -> None:
    """A short host name is passed to the probe, not rejected up front.

    ``pi`` or ``hub`` are perfectly ordinary LAN names, so whether a host is
    usable is for the connection test to decide.
    """

    with patch(
        "homeassistant.components.habitron.config_flow.network.async_get_source_ip",
        new=AsyncMock(return_value="10.0.0.5"),
    ):
        info = await validate_input(hass, {CONF_HOST: "pi"})

    assert info == {"title": MOCK_NAME}


async def test_validate_input_host_not_found_for_dns_failure(
    hass: HomeAssistant,
) -> None:
    """An unresolvable host surfaces as ``HostNotFound``, not ``CannotConnect``.

    ``get_host_ip`` wraps a ``socket.gaierror`` into ``HabitronConnectionError``,
    so resolving the name explicitly is the only place the DNS failure can be
    told apart from a plain connection failure.
    """

    with (
        patch(
            "homeassistant.components.habitron.config_flow.network.async_get_source_ip",
            new=AsyncMock(return_value="10.0.0.5"),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.get_host_ip",
            new=AsyncMock(side_effect=HabitronConnectionError("cannot resolve")),
        ),
        pytest.raises(HostNotFound),
    ):
        await validate_input(
            hass,
            {CONF_HOST: MOCK_HOST},
        )


async def test_validate_input_connection_failure_is_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """A resolvable host that fails the probe is ``CannotConnect``, not host_not_found.

    ``test_connection`` wraps the failure into ``HabitronError``; the earlier
    name resolution succeeded, so this must not be mistaken for a bad name.
    """

    with (
        patch(
            "homeassistant.components.habitron.config_flow.network.async_get_source_ip",
            new=AsyncMock(return_value="10.0.0.5"),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.get_host_ip",
            new=AsyncMock(return_value=MOCK_HOST),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.test_connection",
            new=AsyncMock(side_effect=HabitronError("hub unreachable")),
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(
            hass,
            {CONF_HOST: MOCK_HOST},
        )


def _fake_gethostbyname(host: str) -> str:
    """Stand in for LAN name resolution; unknown names fail as they really do."""
    if host == MOCK_HOST_HOSTNAME:
        return MOCK_HOST
    raise socket.gaierror(f"unknown host {host}")


async def test_is_device_already_configured_host_match(hass: HomeAssistant) -> None:
    """A pre-existing entry whose host matches reports as configured."""

    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={CONF_HOST: MOCK_HOST},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    with patch(
        "homeassistant.components.habitron.config_flow.socket.gethostbyname",
        _fake_gethostbyname,
    ):
        assert await flow._is_device_already_configured(MOCK_HOST) is True
        assert await flow._is_device_already_configured("other-host") is False


async def test_is_device_already_configured_resolves_hostname(
    hass: HomeAssistant,
) -> None:
    """A host name resolving to a configured IP counts as already configured.

    SSDP stores the IP it discovered the hub at; entering the host name that
    points at it must not create a second entry for the same hub.
    """

    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={CONF_HOST: MOCK_HOST},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    with patch(
        "homeassistant.components.habitron.config_flow.socket.gethostbyname",
        _fake_gethostbyname,
    ):
        assert await flow._is_device_already_configured(MOCK_HOST_HOSTNAME) is True


async def test_is_device_already_configured_skips_entry_without_host(
    hass: HomeAssistant,
) -> None:
    """An entry carrying no host is skipped rather than compared."""

    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    assert await flow._is_device_already_configured(MOCK_HOST) is False


async def test_is_device_already_configured_matches_local_sentinel(
    hass: HomeAssistant,
) -> None:
    """A hub stored as the ``local`` sentinel is matched by its own IP.

    ``local`` means "on Home Assistant's own machine", so entering that machine's
    address addresses the very same hub.
    """

    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={CONF_HOST: "local"},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    with patch(
        "homeassistant.components.habitron.config_flow.network."
        "async_get_enabled_source_ips",
        new=AsyncMock(return_value=[IPv4Address(MOCK_HOST)]),
    ):
        assert await flow._is_device_already_configured(MOCK_HOST) is True


async def test_local_sentinel_matches_any_local_ip_multi_homed(
    hass: HomeAssistant,
) -> None:
    """A hub stored as ``local`` matches *any* of HA's local addresses.

    A SmartCenter add-on host with both LAN and WLAN active exposes several
    local IPs; entering the hub via a non-primary one must still resolve to the
    same ``local`` entry, not create a duplicate.
    """
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={CONF_HOST: "local"},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    with patch(
        "homeassistant.components.habitron.config_flow.network."
        "async_get_enabled_source_ips",
        new=AsyncMock(
            return_value=[IPv4Address("192.168.1.50"), IPv4Address("10.0.0.9")]
        ),
    ):
        # The WLAN address, not the primary LAN one.
        assert await flow._is_device_already_configured("10.0.0.9") is True


async def test_is_device_already_configured_resolves_hostname_to_local(
    hass: HomeAssistant,
) -> None:
    """A host name resolving to one of HA's own addresses is the ``local`` hub.

    A hub running on the Home Assistant machine is stored under the ``local``
    sentinel. Entering its host name resolves to a local IP, and returning that
    bare IP would make the two look like different hubs -- so the resolved
    address has to collapse to the sentinel as well.
    """
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={CONF_HOST: "local"},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    with (
        patch(
            "homeassistant.components.habitron.config_flow.socket.gethostbyname",
            _fake_gethostbyname,
        ),
        patch(
            "homeassistant.components.habitron.config_flow.network."
            "async_get_enabled_source_ips",
            # MOCK_HOST_HOSTNAME resolves to MOCK_HOST, which is one of ours.
            new=AsyncMock(return_value=[IPv4Address(MOCK_HOST)]),
        ),
    ):
        assert await flow._is_device_already_configured(MOCK_HOST_HOSTNAME) is True


async def test_is_device_already_configured_ip_match(hass: HomeAssistant) -> None:
    """A pre-existing entry whose host equals the IP reports as configured."""

    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={CONF_HOST: "10.0.0.1"},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    with patch(
        "homeassistant.components.habitron.config_flow.socket.gethostbyname",
        _fake_gethostbyname,
    ):
        assert await flow._is_device_already_configured("hub-x", ip="10.0.0.1") is True


async def test_ssdp_discovery_confirm_handles_validate_error(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A confirm step that fails validation with an unexpected error aborts."""
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=ValueError("totally unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_ssdp_discovery_confirm_cannot_connect_retries(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A briefly-offline discovered hub re-shows the confirm form, and the retry works.

    Re-showing the form is only useful if submitting it again reaches the hub;
    stopping at the error would leave that half untested.
    """
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    # The hub answers now: the same flow carries on to an entry.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: MOCK_HOST}


@pytest.mark.parametrize("error", [HostNotFound])
async def test_ssdp_discovery_confirm_host_error_retries(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    error: type[Exception],
) -> None:
    """An unresolved discovery host re-shows the confirm form to retry."""
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_host_not_found_via_validate_input(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A HostNotFound raised from validate_input maps to ``host_not_found``."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=HostNotFound("dns"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
    assert result["errors"] == {"base": "host_not_found"}


async def test_user_flow_truly_unknown_exception_maps_to_unknown(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An exception type the user step does not know surfaces as ``unknown``."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=ValueError("totally unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_unexpected_exception_maps_to_unknown(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An unexpected error from the probe propagates and surfaces as ``unknown``."""
    mock_habitron_client.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_step_prefills_host_from_discovery(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """The user step pre-fills the host field from a discovered device."""
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": "10.0.0.99", "serial": "s"}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # The form's data-schema default should now reflect the discovered ip.
    schema = result["data_schema"].schema
    # Find the CONF_HOST default by walking the schema vol.Required keys.
    default = None
    for key in schema:
        if getattr(key, "schema", None) == CONF_HOST:
            default = key.default()
            break
    assert default == "10.0.0.99"


@pytest.mark.parametrize(
    "error",
    [
        HabitronError("scan blew up"),
        # A missing route/interface surfaces as OSError from the own-IP lookup.
        OSError("network is unreachable"),
    ],
)
async def test_user_step_survives_discovery_failure(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    error: Exception,
) -> None:
    """A discovery error is swallowed so the manual host form is still shown."""
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


_HUB_MAC = "d83addbae72e"


def _store_entry(hass: HomeAssistant, unique_id: str, host: str) -> None:
    """Add a configured hub keyed by ``unique_id`` at ``host``."""
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=unique_id,
        data={CONF_HOST: host},
    ).add_to_hass(hass)


async def _run_user_flow(
    hass: HomeAssistant, probed: str | None = None
) -> config_entries.ConfigFlowResult:
    """Run the manual flow to completion, with ``probed`` found on the network."""
    devices = [{"ip": MOCK_HOST, "serial": probed}] if probed else []
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=devices),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )
        await hass.async_block_till_done()
    return result


async def _start_ssdp_flow(
    hass: HomeAssistant, upnp: dict[str, str]
) -> config_entries.ConfigFlowResult:
    """Start a discovery flow for the hub advertising ``upnp``."""
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp=upnp,
    )
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=discovery
        )
        await hass.async_block_till_done()
    return result


async def test_user_flow_identity_when_nothing_configured(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """The manual flow keys on the hub's MAC."""
    mock_hub_mac.return_value = _HUB_MAC

    result = await _run_user_flow(hass, None)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _HUB_MAC


@pytest.mark.parametrize(
    ("stored_id", "stored_host", "expect_id"),
    [
        (_HUB_MAC, MOCK_HOST, _HUB_MAC),
        (_HUB_MAC, "192.168.1.99", _HUB_MAC),
    ],
    ids=["same MAC, same address", "same MAC, address moved"],
)
async def test_user_flow_recognises_a_configured_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
    stored_id: str,
    stored_host: str,
    expect_id: str,
) -> None:
    """A hub that is already configured is never offered a second time."""
    mock_hub_mac.return_value = _HUB_MAC
    _store_entry(hass, stored_id, stored_host)

    result = await _run_user_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == expect_id
    # A hub found again always carries the address it answered at.
    assert entry.data[CONF_HOST] == MOCK_HOST


async def test_user_flow_adds_a_second_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """A different hub is added rather than matched against the configured one."""
    mock_hub_mac.return_value = _HUB_MAC
    _store_entry(hass, "001122334455", "192.168.1.99")

    result = await _run_user_flow(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _HUB_MAC


async def test_ssdp_flow_identity_when_nothing_configured(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """Discovery derives the same identity as the manual flow.

    The advertised UPnP fields play no part in it: ``async_step_ssdp`` takes
    the address out of the announcement and probes the hub for its MAC.
    """
    mock_hub_mac.return_value = _HUB_MAC

    result = await _start_ssdp_flow(hass, {ATTR_UPNP_UDN: MOCK_UDN})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["result"].unique_id == _HUB_MAC


@pytest.mark.parametrize(
    ("stored_id", "stored_host"),
    [
        (_HUB_MAC, MOCK_HOST),
        (_HUB_MAC, "192.168.1.99"),
    ],
    ids=["same MAC, same address", "same MAC, address moved"],
)
async def test_ssdp_flow_recognises_a_configured_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
    stored_id: str,
    stored_host: str,
) -> None:
    """Discovery of a configured hub aborts, whichever id the entry carries."""
    mock_hub_mac.return_value = _HUB_MAC
    _store_entry(hass, stored_id, stored_host)

    result = await _start_ssdp_flow(hass, {ATTR_UPNP_UDN: MOCK_UDN})

    assert result["type"] is FlowResultType.ABORT
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == _HUB_MAC


async def test_user_flow_without_a_mac_reports_it_on_the_form(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """A hub that reports no MAC has no identity, so no entry is created.

    Shown on the form rather than aborted: updating the hub's software makes
    the very same input work, so the user can simply try again.
    """
    mock_hub_mac.return_value = None

    result = await _run_user_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_mac_address"}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_ssdp_flow_without_a_mac_is_aborted(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """Discovery of a hub without a MAC is dropped rather than offered.

    Two such hubs would be indistinguishable, so offering one would risk
    binding the second to the first one's entry.
    """
    mock_hub_mac.return_value = None
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN, ATTR_UPNP_SERIAL: MOCK_SERIAL},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=discovery
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_mac_address"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_probe_host_dials_a_name_that_does_not_resolve(
    hass: HomeAssistant,
) -> None:
    """An unresolvable name is passed on as typed rather than dropped.

    Resolving is only there so the hub's reply can be matched to what was
    dialled; when it fails, the name may still be reachable (a hosts entry, a
    resolver the executor cannot see), so the probe gets it unchanged.
    """
    flow = ConfigFlow()
    flow.hass = hass
    with (
        patch(
            "homeassistant.components.habitron.config_flow.socket.gethostbyname",
            side_effect=OSError("no such host"),
        ),
        patch(
            "homeassistant.components.habitron.config_flow._async_hub_mac",
            new=AsyncMock(return_value=None),
        ) as hub_mac,
    ):
        assert await flow._async_hub_identity("nosuchhub") is None

    hub_mac.assert_awaited_once_with("nosuchhub")


async def test_ssdp_flow_aborts_when_the_hub_is_unreachable(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """An advertised but unreachable hub is dropped, not offered.

    Without a reachable hub there is no identity, and SSDP re-announces, so the
    flow comes back on its own once the hub answers again.
    """
    mock_hub_mac.side_effect = CannotConnect
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=discovery
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_ssdp_matches_a_migrated_entry_by_its_address(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An entry that has not adopted the hub's MAC yet is still recognised.

    A migrated custom-integration entry keeps its older id -- a serial, or
    ``habitron_<host>`` -- until its first successful setup adopts the MAC. The
    unique-id check does not find it in that window, so without an address
    match the same hub would be offered and configured twice.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"habitron_{MOCK_HOST}",
        data={CONF_HOST: MOCK_HOST},
    )
    entry.add_to_hass(hass)

    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Only one entry, and its identity is left alone -- setup adopts the MAC.
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.unique_id == f"habitron_{MOCK_HOST}"


async def test_user_flow_matches_a_migrated_entry_by_its_address(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """The same hub entered by hand must not become a second entry either."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="HBT-123456",  # a serial, as the custom integration falls back to
        data={CONF_HOST: MOCK_HOST},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_user_flow_recognises_a_migrated_entry_that_also_moved(
    hass: HomeAssistant,
    setup_homeassistant: None,
    device_registry: dr.DeviceRegistry,
    mock_habitron_client: MagicMock,
) -> None:
    """A carried-over entry whose address changed is still the same hub.

    It has not adopted its MAC yet, so the unique-id check does not know it,
    and the address it stores is stale -- which is usually *why* it is sitting
    in a setup retry. With neither matcher seeing it, the hub would be added a
    second time, and the old entry could never adopt the MAC that would resolve
    the duplicate: it cannot reach the hub at all. Its hub device carries the
    MAC, and that survives the move.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="HBT-123456",  # a serial, as the custom integration falls back to
        data={CONF_HOST: "192.168.1.99"},  # the address it had before the move
    )
    entry.add_to_hass(hass)
    # Registered the way the custom integration does it, in the hub's own
    # notation -- the registry normalises it, and the flow looks it up with the
    # bare uid.
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MOCK_MAC)},
        identifiers={(DOMAIN, "HBT-123456")},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data[CONF_HOST] == MOCK_HOST


async def test_user_flow_adds_a_different_hub_at_a_recycled_address(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """An address DHCP handed to another hub must not match the old entry.

    The host fallback is there for an entry carried over from the custom
    integration, which has no MAC identity yet. An entry that already carries
    one is identified by it -- matching it on the address as well would abort
    the new hub and rewrite the old entry onto a device that is not its own.
    """
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,  # hub A, already keyed by its MAC
        data={CONF_HOST: MOCK_HOST},
    ).add_to_hass(hass)

    # Hub B answers at the address hub A used to have.
    mock_hub_mac.return_value = "112233445566"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


def _entry_in_backoff(
    hass: HomeAssistant, unique_id: str, host: str
) -> MockConfigEntry:
    """Add an entry that is sitting out a setup-retry backoff.

    Such an entry has no update listener -- the integration only registers one
    once setup has succeeded -- so nothing picks up a host a flow writes to it.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=unique_id,
        data={CONF_HOST: host},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, config_entries.ConfigEntryState.SETUP_RETRY)
    return entry


@pytest.mark.parametrize(
    ("stored_id", "stored_host"),
    [
        # Matched by address, so the entry has to be at the one discovered --
        # a legacy entry that also moved cannot be recognised at all.
        (f"habitron_{MOCK_HOST}", MOCK_HOST),
        # Matched by MAC, so the address is free to have moved.
        (MOCK_UID, "192.168.1.99"),
    ],
    ids=["host-matched legacy entry", "MAC-keyed entry"],
)
async def test_ssdp_rediscovery_reloads_a_retrying_entry(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    stored_id: str,
    stored_host: str,
) -> None:
    """A hub announcing itself must not leave its entry in backoff.

    Config entries reload a retrying entry themselves for the discovery
    sources, so the abort is enough here -- and the count is what pins it:
    scheduling a reload of our own in ``async_step_ssdp`` would make it two.
    """
    entry = _entry_in_backoff(hass, stored_id, stored_host)

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=SsdpServiceInfo(
                ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
                ssdp_st="urn:habitron-com:device:SmartHub:1",
                ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
                upnp={ATTR_UPNP_UDN: MOCK_UDN},
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_reload.assert_called_once_with(entry.entry_id)


async def test_user_flow_reloads_a_retrying_entry(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """Re-entering a moved hub by hand must not leave its entry in backoff.

    The user source is not one of the discovery sources config entries reload
    on their own, and the entry has no update listener to pick up the new host,
    so the flow has to schedule the reload itself.
    """
    entry = _entry_in_backoff(hass, MOCK_UID, "192.168.1.99")

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: MOCK_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_reload.assert_called_once_with(entry.entry_id)
