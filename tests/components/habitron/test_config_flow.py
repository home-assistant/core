"""Tests for the Habitron config flow."""

from ipaddress import IPv4Address
import socket
from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import HabitronConnectionError, HabitronError, HabitronTimeoutError
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
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import (
    MOCK_CONFIG_DATA,
    MOCK_HOST,
    MOCK_HOST_HOSTNAME,
    MOCK_NAME,
    MOCK_SERIAL,
    MOCK_UDN,
)

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
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


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An identical config aborts with ``already_configured``.

    The user step falls back to ``habitron_{host}`` for the unique id
    when no discovery response arrives, so we register an existing
    entry with that same id to trigger the abort path.
    """
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"habitron_{MOCK_HOST}",
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


async def test_user_flow_duplicate_host_of_ssdp_entry(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """Manually adding the host of an SSDP-configured hub aborts.

    An SSDP entry is keyed by its UDN, so the serial/host unique id derived
    by the manual step does not match it and ``_abort_if_unique_id_configured``
    does not fire. The host-based duplicate guard must still abort instead of
    creating a second entry (and connection) for the same hub.
    """
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UDN,
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


async def test_ssdp_discovery_with_udn(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """Without a UPnP serial, SSDP discovery falls back to the UDN."""
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
    assert result["step_id"] == "discovery_confirm"

    # Confirm step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == MOCK_UDN


async def test_ssdp_prefers_serial_over_udn(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """With both advertised, the serial wins over the UDN.

    The manual and UDP paths key on the serial, so preferring the UDN here
    would leave the same hub unmatched once its IP changes -- and offered as a
    duplicate.
    """
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN, ATTR_UPNP_SERIAL: MOCK_SERIAL},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    assert result["result"].unique_id == MOCK_SERIAL


async def test_user_step_empty_probe_serial_falls_back_to_host_id(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A blank serial is no identifier and must not become the unique id.

    Every hub answering with ``"serial": ""`` would otherwise share one empty
    unique id and collide with each other.
    """
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": ""}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"habitron_{MOCK_HOST}"


@pytest.mark.parametrize(
    ("submitted", "expected_unique_id"),
    [
        # Resolves to the probed address -> the serial is picked up.
        (MOCK_HOST_HOSTNAME, MOCK_SERIAL),
        # Does not resolve at all -> host-based fallback, no probe match.
        ("nosuchhub", "habitron_nosuchhub"),
    ],
)
async def test_user_step_resolves_hostname_for_the_probe_match(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
    submitted: str,
    expected_unique_id: str,
) -> None:
    """A submitted host name still picks up the probed serial.

    The UDP probe answers with an address, so comparing the raw name against it
    would never match -- the hub would get a host-based id that breaks as soon
    as its name or address changes. A name that does not resolve simply keeps
    the fallback.
    """
    with (
        patch(
            "homeassistant.components.habitron.config_flow.discover_smarthubs",
            new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": MOCK_SERIAL}]),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.socket.gethostbyname",
            _fake_gethostbyname,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: submitted}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == expected_unique_id


async def test_ssdp_discovery_serial_fallback(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """When no UDN, the UPnP serialNumber is used."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_SERIAL: MOCK_SERIAL},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == MOCK_SERIAL


async def test_ssdp_keeps_stable_id_when_discovery_yields_only_host_fallback(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A stable id is preserved when this discovery produces only the fallback.

    With no UDN/serial this run, ``unique_id`` is ``habitron_<host>``.
    Overwriting an existing stable id with it would leave the entry unmatched
    after a DHCP change, offering the same hub as a duplicate.
    """
    stable_entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_SERIAL,
        data={**MOCK_CONFIG_DATA, CONF_HOST: MOCK_HOST},
    )
    stable_entry.add_to_hass(hass)

    discovery = SsdpServiceInfo(
        ssdp_usn="dummy::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={},  # no UDN, no serial -> unique_id falls back to habitron_<host>
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # The stable serial id must be kept, not downgraded to the host fallback.
    assert stable_entry.unique_id == MOCK_SERIAL


async def test_ssdp_legacy_unique_id_migrated(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A pre-existing host-based entry gets migrated on rediscovery."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"habitron_{MOCK_HOST}",
        data=MOCK_CONFIG_DATA,
    )
    legacy_entry.add_to_hass(hass)

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
    # Old host-based entry should already have been rewritten and the
    # flow aborted as "already configured" against the new id.
    await hass.async_block_till_done()
    assert legacy_entry.unique_id == MOCK_UDN
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_matches_entry_stored_under_host_name(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A hub added manually by name is recognised when SSDP reports its IP.

    The manual step falls back to ``habitron_<host>`` when no serial can be
    read, so the UDN from the discovery does not match. Without canonicalising
    the *configured* host too, ``smarthub.local`` never matches the reported
    ``192.168.1.50`` and the user is offered a duplicate of a hub that is
    already set up.
    """
    named_entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"habitron_{MOCK_HOST_HOSTNAME}",
        data={**MOCK_CONFIG_DATA, CONF_HOST: MOCK_HOST_HOSTNAME},
    )
    named_entry.add_to_hass(hass)

    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    with patch(
        "homeassistant.components.habitron.config_flow.socket.gethostbyname",
        _fake_gethostbyname,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # The entry is adopted under the stable discovery id.
    assert named_entry.unique_id == MOCK_UDN


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
        unique_id=MOCK_UDN,
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


async def test_ssdp_keeps_a_serial_id_when_only_a_udn_is_advertised(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A serial-keyed entry is not downgraded to a UDN.

    Rewriting it would flip the id back and forth as discoveries with and
    without a serial alternate; only a host-based fallback may be replaced.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_SERIAL,
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
    assert entry.unique_id == MOCK_SERIAL


async def test_user_step_updates_the_stored_host_of_a_known_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """Re-adding a known hub at a new address moves the entry to it.

    The serial identifies the same hub, so aborting without the update would
    leave the entry pointing at the address it no longer answers on.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_SERIAL,
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
    client.get_smhub_info = AsyncMock(
        return_value={"hardware": {"network": {"lan mac": reported}}}
    )
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "homeassistant.components.habitron.config_flow.HabitronClient",
        return_value=client,
    ):
        assert await _async_hub_mac(MOCK_HOST) == expected


async def test_hub_mac_unreachable_returns_none() -> None:
    """A hub that cannot be read yields no MAC instead of raising."""
    with patch(
        "homeassistant.components.habitron.config_flow.HabitronClient",
        side_effect=OSError("no route"),
    ):
        assert await _async_hub_mac(MOCK_HOST) is None


@pytest.mark.parametrize(
    ("reported_mac", "expected_type"),
    [
        # The same hub, however it was reached before.
        ("d83addbae72e", FlowResultType.ABORT),
        # A different hub is a genuinely new device.
        ("001122334455", FlowResultType.CREATE_ENTRY),
        # Unreachable hub: fall through instead of guessing.
        (None, FlowResultType.CREATE_ENTRY),
    ],
)
async def test_user_step_mac_match_normalises_and_falls_through(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
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
    mock_smart_hub_setup: None,
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
    mock_smart_hub_setup: None,
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
    mock_smart_hub_setup: None,
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
    mock_smart_hub_setup: None,
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


async def test_ssdp_prefers_the_probed_serial_over_the_udn(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A UDN is only used when no serial can be had at all.

    The manual path keys on the UDP serial. If discovery keyed the same hub by
    its UDN instead, an address change would leave neither the ids nor the
    stored hosts matching -- and the hub could be added twice.
    """
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": MOCK_SERIAL}]),
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

    assert result["result"].unique_id == MOCK_SERIAL


async def test_user_step_unignores_a_mac_keyed_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
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


async def test_ssdp_discovery_falls_back_to_discovery_serial(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A discovery without UDN/serial picks the serial from the network probe."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={},
    )

    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": "UDP-SER-1"}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == "UDP-SER-1"


async def test_ssdp_discovery_no_udn_no_probe_falls_back_to_host_id(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """Without UDN, serial or matching probe device, the host string is used."""
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
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == f"habitron_{MOCK_HOST}"


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
    """A briefly-offline discovered hub re-shows the confirm form to retry."""
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


async def test_user_flow_own_ip_canonicalizes_unique_id(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """An own-IP host is canonicalized to ``local`` before deriving the id.

    ``validate_input`` rewrites an own IP to the ``local`` sentinel, so the
    fallback unique_id must be built from the canonical host to stay consistent.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # 192.168.1.10 is the (mocked) own source IP.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.10"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "local"
    assert result["result"].unique_id == "habitron_local"


async def test_user_flow_picks_up_serial_from_discovery_probe(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> None:
    """A matching discovery serial becomes the unique id."""
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": "SERIAL-X"}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "SERIAL-X"


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


@pytest.mark.parametrize(
    ("hub_mac", "probed", "expect_id"),
    [
        (_HUB_MAC, None, _HUB_MAC),
        (None, MOCK_SERIAL, MOCK_SERIAL),
        (None, None, f"habitron_{MOCK_HOST}"),
    ],
    ids=["MAC readable", "only a serial", "nothing at all"],
)
async def test_user_flow_identity_when_nothing_configured(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
    hub_mac: str | None,
    probed: str | None,
    expect_id: str,
) -> None:
    """The manual flow keys on the MAC, falling back only when it cannot read one."""
    mock_hub_mac.return_value = hub_mac

    result = await _run_user_flow(hass, probed)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == expect_id


@pytest.mark.parametrize(
    ("stored_id", "stored_host", "expect_id"),
    [
        (_HUB_MAC, MOCK_HOST, _HUB_MAC),
        (_HUB_MAC, "192.168.1.99", _HUB_MAC),
        # A pre-MAC entry: the address still matches, so it is recognised.
        (MOCK_SERIAL, MOCK_HOST, MOCK_SERIAL),
    ],
    ids=["same MAC, same address", "same MAC, address moved", "legacy serial id"],
)
async def test_user_flow_recognises_a_configured_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
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
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
) -> None:
    """A different hub is added rather than matched against the configured one."""
    mock_hub_mac.return_value = _HUB_MAC
    _store_entry(hass, "001122334455", "192.168.1.99")

    result = await _run_user_flow(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _HUB_MAC


@pytest.mark.parametrize(
    ("hub_mac", "upnp", "expect_id"),
    [
        (_HUB_MAC, {ATTR_UPNP_UDN: MOCK_UDN}, _HUB_MAC),
        (None, {ATTR_UPNP_UDN: MOCK_UDN}, MOCK_UDN),
        (None, {ATTR_UPNP_SERIAL: MOCK_SERIAL}, MOCK_SERIAL),
    ],
    ids=["MAC readable", "only a UDN", "only a UPnP serial"],
)
async def test_ssdp_flow_identity_when_nothing_configured(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
    mock_hub_mac: AsyncMock,
    hub_mac: str | None,
    upnp: dict[str, str],
    expect_id: str,
) -> None:
    """Discovery derives the same identity as the manual flow."""
    mock_hub_mac.return_value = hub_mac

    result = await _start_ssdp_flow(hass, upnp)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["result"].unique_id == expect_id


@pytest.mark.parametrize(
    ("stored_id", "stored_host"),
    [
        (_HUB_MAC, "192.168.1.99"),
        (f"habitron_{MOCK_HOST}", MOCK_HOST),
    ],
    ids=["same MAC, address moved", "legacy host id"],
)
async def test_ssdp_flow_recognises_a_configured_hub(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
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
