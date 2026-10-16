"""Tests for the Mitsubishi Comfort repairs flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from mitsubishi_comfort import DeviceInfo
from mitsubishi_comfort.exceptions import DeviceConnectionError
import pytest

from homeassistant.components.mitsubishi_comfort.const import (
    CONF_ADDRESSES,
    CONF_CREDENTIALS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.setup import async_setup_component

from .conftest import MOCK_MAC, MOCK_PASSWORD, MOCK_SERIAL, MOCK_USERNAME

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("mock_setup_integration")

# The per-device IP fields are keyed by formatted MAC (dynamic), so they have
# no static label in strings.json; ignore that in the translation check.
IGNORE_FORM_TRANSLATIONS = [
    "component.mitsubishi_comfort.issues.missing_address.fix_flow.step.addresses.data.",
    "component.mitsubishi_comfort.issues.missing_address.fix_flow.step.addresses.data_description.",
]


def _second_device_info() -> DeviceInfo:
    """Build a second fully-credentialed device without a LAN address."""
    return DeviceInfo(
        serial="SERIAL002",
        label="Bedroom",
        address="",
        mac="11:22:33:44:55:66",
        unit_type="ductless",
        password="dGVzdHBhc3M=",
        crypto_serial="0102030405060708090a",
    )


async def _setup_addressless_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry whose device has no LAN address, raising the issue."""
    assert await async_setup_component(hass, "repairs", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        unique_id="user-12345",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
@pytest.mark.parametrize(
    "invalid_value",
    [
        pytest.param("not-an-ip", id="not_an_ip"),
        pytest.param("2001:db8::1", id="ipv6"),
    ],
)
async def test_fix_flow_sets_missing_address(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    invalid_value: str,
) -> None:
    """Test the fix flow records a manually entered IP and resolves the issue.

    Non-IPv4 input is rejected: the local API URL is built without IPv6
    brackets, so an IPv6 literal can never work.
    """
    entry = await _setup_addressless_entry(hass)
    issue_id = f"missing_address_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    flow_id = data["flow_id"]
    assert data["step_id"] == "addresses"
    # The fields are labeled by raw MAC, so the description must pair each MAC
    # with its device name for the user to tell the fields apart.
    assert dr.format_mac(MOCK_MAC) in data["description_placeholders"]["devices"]

    data = await process_repair_fix_flow(
        client, flow_id, json={dr.format_mac(MOCK_MAC): invalid_value}
    )
    assert data["errors"] == {dr.format_mac(MOCK_MAC): "invalid_ip"}

    with patch(
        "homeassistant.components.mitsubishi_comfort.repairs.probe_candidate_ips",
        return_value={MOCK_SERIAL: "192.168.1.50"},
    ) as mock_probe:
        data = await process_repair_fix_flow(
            client, flow_id, json={dr.format_mac(MOCK_MAC): "192.168.1.50"}
        )
    assert data["type"] == "create_entry"
    assert mock_probe.call_args.kwargs["session"] is async_get_clientsession(hass)
    # The probe must authenticate with the cached local secrets; without them
    # every correct IP would be rejected as cannot_connect.
    probed = mock_probe.call_args.args[0]
    assert probed[MOCK_SERIAL].password == "dGVzdHBhc3M="
    assert probed[MOCK_SERIAL].crypto_serial == "0102030405060708090a"
    await hass.async_block_till_done()

    assert entry.data[CONF_ADDRESSES][dr.format_mac(MOCK_MAC)] == "192.168.1.50"
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_blank_field_keeps_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test leaving a field blank keeps the device addressless.

    The repairs framework deletes the issue when the flow completes; the
    reload the flow schedules re-creates it while any device still lacks an
    address.
    """
    entry = await _setup_addressless_entry(hass)
    issue_id = f"missing_address_{entry.entry_id}"

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    data = await process_repair_fix_flow(client, data["flow_id"], json={})
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert not entry.data.get(CONF_ADDRESSES)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
@pytest.mark.parametrize(
    ("submission", "issue_expected"),
    [
        pytest.param({}, True, id="still_addressless"),
        pytest.param(
            {dr.format_mac(MOCK_MAC): "192.168.1.50"}, False, id="fully_addressed"
        ),
    ],
)
async def test_fix_flow_failed_reload_restores_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    submission: dict[str, str],
    issue_expected: bool,
) -> None:
    """Test a reload whose unload fails restores the missing-address issue.

    The repairs framework deletes the issue when the flow finishes, and a
    failed unload stops the reload before setup can re-create it — so the
    reload task restores the issue itself, but only while devices actually
    remain addressless.
    """
    entry = await _setup_addressless_entry(hass)
    issue_id = f"missing_address_{entry.entry_id}"

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.repairs.probe_candidate_ips",
            return_value={MOCK_SERIAL: "192.168.1.50"},
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.async_unload_entry",
            return_value=False,
        ),
    ):
        data = await process_repair_fix_flow(client, data["flow_id"], json=submission)
        assert data["type"] == "create_entry"
        await hass.async_block_till_done()

    assert bool(issue_registry.async_get_issue(DOMAIN, issue_id)) is issue_expected


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_retry_on_wedged_entry_keeps_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repeat repair attempt on a FAILED_UNLOAD entry keeps the issue.

    The first failed reload leaves the entry non-recoverable, so the second
    attempt's reload raises OperationNotAllowed instead of returning False;
    the issue must survive that path too or the still-addressless entry loses
    its only fix-flow path until restart.
    """
    entry = await _setup_addressless_entry(hass)
    issue_id = f"missing_address_{entry.entry_id}"

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    with patch(
        "homeassistant.components.mitsubishi_comfort.async_unload_entry",
        return_value=False,
    ):
        data = await process_repair_fix_flow(client, data["flow_id"], json={})
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    data = await process_repair_fix_flow(client, data["flow_id"], json={})
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_failed_reload_ignores_partial_records(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
    mock_device_info: DeviceInfo,
) -> None:
    """Test a partial credential record cannot trigger issue restoration.

    A MAC-less record never gets an address, but it also cannot be offered in
    the fix flow, so restoring the issue for it would create an unfixable
    repair.
    """
    mock_account, _ = mock_setup_integration
    mock_account.discover_devices.return_value = {
        MOCK_SERIAL: mock_device_info,
        "SERIAL002": DeviceInfo(
            serial="SERIAL002",
            label="Bedroom",
            address="",
            mac="",
            unit_type="ductless",
            password="dGVzdHBhc3M=",
            crypto_serial="0102030405060708090a",
        ),
    }
    entry = await _setup_addressless_entry(hass)
    issue_id = f"missing_address_{entry.entry_id}"
    mac = dr.format_mac(MOCK_MAC)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.repairs.probe_candidate_ips",
            return_value={MOCK_SERIAL: "192.168.1.50"},
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.async_unload_entry",
            return_value=False,
        ),
    ):
        data = await process_repair_fix_flow(
            client, data["flow_id"], json={mac: "192.168.1.50"}
        )
        assert data["type"] == "create_entry"
        await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_lists_only_addressless_devices(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
    mock_device_info: DeviceInfo,
) -> None:
    """Test the form omits devices that already have a stored address."""
    mock_account, _ = mock_setup_integration
    mock_account.discover_devices.return_value = {
        MOCK_SERIAL: mock_device_info,
        "SERIAL002": _second_device_info(),
    }
    assert await async_setup_component(hass, "repairs", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_ADDRESSES: {dr.format_mac(MOCK_MAC): "192.168.1.100"},
        },
        unique_id="user-12345",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, f"missing_address_{entry.entry_id}"
    )

    second_mac = dr.format_mac("11:22:33:44:55:66")
    assert [field["name"] for field in data["data_schema"]] == [second_mac]
    assert data["description_placeholders"]["devices"] == f"Bedroom ({second_mac})"


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_offers_cached_devices_before_first_discovery(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test the form offers cached devices when no discovery ever succeeded.

    The registry is empty then, so the fields fall back to the credential
    cache with the serial as the label; a registry-only form would render
    zero fields and make the repair a dead-end loop while the cloud is down.
    """
    assert await async_setup_component(hass, "repairs", {})
    mock_account, _ = mock_setup_integration
    mock_account.login.side_effect = DeviceConnectionError("cloud down")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_CREDENTIALS: {
                MOCK_SERIAL: {
                    "password": "dGVzdHBhc3M=",
                    "crypto_serial": "0102030405060708090a",
                    "mac": MOCK_MAC,
                }
            },
        },
        unique_id="user-12345",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    issue_id = f"missing_address_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    mac = dr.format_mac(MOCK_MAC)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert [field["name"] for field in data["data_schema"]] == [mac]
    assert data["description_placeholders"]["devices"] == f"{MOCK_SERIAL} ({mac})"

    with patch(
        "homeassistant.components.mitsubishi_comfort.repairs.probe_candidate_ips",
        return_value={MOCK_SERIAL: "192.168.1.50"},
    ):
        data = await process_repair_fix_flow(
            client, data["flow_id"], json={mac: "192.168.1.50"}
        )
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert entry.data[CONF_ADDRESSES][mac] == "192.168.1.50"
    # Every cached device is addressed now, so the failed reload (the cloud
    # is still down) must not resurrect the issue.
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_suggests_cached_ip(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the form pre-fills an IP the DHCP cache saw after setup."""
    entry = await _setup_addressless_entry(hass)
    issue_id = f"missing_address_{entry.entry_id}"

    client = await hass_client()
    with patch(
        "homeassistant.components.mitsubishi_comfort.repairs.async_discovered_service_info",
        return_value=[
            DhcpServiceInfo(
                ip="10.0.0.5",
                hostname="kumo",
                macaddress=MOCK_MAC.replace(":", "").lower(),
            )
        ],
    ):
        data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    assert data["step_id"] == "addresses"
    assert data["data_schema"][0]["description"] == {"suggested_value": "10.0.0.5"}


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_keeps_address_discovered_during_probe(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
    mock_device_info: DeviceInfo,
) -> None:
    """Test an address stored by DHCP during the probe await is not erased."""
    second = _second_device_info()
    mock_account, _ = mock_setup_integration
    mock_account.discover_devices.return_value = {
        "SERIAL001": mock_device_info,
        "SERIAL002": second,
    }
    entry = await _setup_addressless_entry(hass)
    second_mac = dr.format_mac(second.mac)

    async def _probe_with_concurrent_discovery(
        *args: object, **kwargs: object
    ) -> dict[str, str]:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_ADDRESSES: {second_mac: "192.168.1.60"}},
        )
        return {MOCK_SERIAL: "192.168.1.50"}

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, f"missing_address_{entry.entry_id}"
    )
    with patch(
        "homeassistant.components.mitsubishi_comfort.repairs.probe_candidate_ips",
        side_effect=_probe_with_concurrent_discovery,
    ):
        data = await process_repair_fix_flow(
            client, data["flow_id"], json={dr.format_mac(MOCK_MAC): "192.168.1.50"}
        )
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert entry.data[CONF_ADDRESSES] == {
        second_mac: "192.168.1.60",
        dr.format_mac(MOCK_MAC): "192.168.1.50",
    }


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_rejects_unreachable_address(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test an address whose device fails the authenticated probe is rejected.

    Storing an unverified address would suppress this repair while the entry
    is stuck retrying its first refresh, with no UI path left to correct it.
    """
    entry = await _setup_addressless_entry(hass)

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, f"missing_address_{entry.entry_id}"
    )
    with patch(
        "homeassistant.components.mitsubishi_comfort.repairs.probe_candidate_ips",
        return_value={},
    ) as mock_probe:
        data = await process_repair_fix_flow(
            client, data["flow_id"], json={dr.format_mac(MOCK_MAC): "192.168.1.77"}
        )

    assert data["errors"] == {dr.format_mac(MOCK_MAC): "cannot_connect"}
    assert mock_probe.call_args.args[1] == ["192.168.1.77"]
    # The re-rendered form keeps what the user typed.
    assert data["data_schema"][0]["description"] == {"suggested_value": "192.168.1.77"}
    assert not entry.data.get(CONF_ADDRESSES)


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_flags_each_unreachable_field(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
    mock_device_info: DeviceInfo,
) -> None:
    """Test only the fields whose probes fail carry the connection error.

    With several devices submitted, a base error would not tell the user
    which address is wrong.
    """
    second = _second_device_info()
    mock_account, _ = mock_setup_integration
    mock_account.discover_devices.return_value = {
        MOCK_SERIAL: mock_device_info,
        "SERIAL002": second,
    }
    entry = await _setup_addressless_entry(hass)
    second_mac = dr.format_mac(second.mac)

    async def _probe_first_only(
        devices: dict[str, DeviceInfo], ips: list[str], **kwargs: object
    ) -> dict[str, str]:
        serial = next(iter(devices))
        return {serial: ips[0]} if serial == MOCK_SERIAL else {}

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, f"missing_address_{entry.entry_id}"
    )
    with patch(
        "homeassistant.components.mitsubishi_comfort.repairs.probe_candidate_ips",
        side_effect=_probe_first_only,
    ):
        data = await process_repair_fix_flow(
            client,
            data["flow_id"],
            json={
                dr.format_mac(MOCK_MAC): "192.168.1.50",
                second_mac: "192.168.1.60",
            },
        )

    assert data["errors"] == {second_mac: "cannot_connect"}
    assert not entry.data.get(CONF_ADDRESSES)


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_concurrent_lease_wins_over_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a lease DHCP stored during the probe beats the form entry.

    Live discovery saw the device after the user typed the address, so the
    stored lease is the fresher fact for the same MAC.
    """
    entry = await _setup_addressless_entry(hass)
    mac = dr.format_mac(MOCK_MAC)

    async def _probe_with_concurrent_lease(
        *args: object, **kwargs: object
    ) -> dict[str, str]:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_ADDRESSES: {mac: "192.168.1.99"}}
        )
        return {MOCK_SERIAL: "192.168.1.50"}

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, f"missing_address_{entry.entry_id}"
    )
    with patch(
        "homeassistant.components.mitsubishi_comfort.repairs.probe_candidate_ips",
        side_effect=_probe_with_concurrent_lease,
    ):
        data = await process_repair_fix_flow(
            client, data["flow_id"], json={mac: "192.168.1.50"}
        )
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert entry.data[CONF_ADDRESSES][mac] == "192.168.1.99"


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_omits_devices_without_secrets(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
    mock_device_info: DeviceInfo,
) -> None:
    """Test the form skips devices whose local secrets are missing.

    A partial record can hold a MAC with no password or cryptoSerial; any
    address entered for it is guaranteed to fail the authenticated probe,
    and setup counts that device as incomplete rather than addressless.
    """
    secretless = DeviceInfo(
        serial="SERIAL002",
        label="Bedroom",
        address="",
        mac="11:22:33:44:55:66",
        unit_type="ductless",
        password="",
        crypto_serial="",
    )
    mock_account, _ = mock_setup_integration
    mock_account.discover_devices.return_value = {
        "SERIAL001": mock_device_info,
        "SERIAL002": secretless,
    }
    entry = await _setup_addressless_entry(hass)

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, f"missing_address_{entry.entry_id}"
    )

    assert data["step_id"] == "addresses"
    assert [field["name"] for field in data["data_schema"]] == [dr.format_mac(MOCK_MAC)]


@pytest.mark.parametrize("ignore_missing_translations", [IGNORE_FORM_TRANSLATIONS])
async def test_fix_flow_omits_devices_no_longer_on_account(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the form skips registry devices the account no longer has.

    Setup prunes the credential cache but leaves old device registry entries,
    so the form intersects with the cache to ask only for current devices.
    """
    entry = await _setup_addressless_entry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "REMOVED01")},
        connections={(dr.CONNECTION_NETWORK_MAC, "99:99:99:99:99:99")},
    )

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, f"missing_address_{entry.entry_id}"
    )

    assert data["step_id"] == "addresses"
    assert [field["name"] for field in data["data_schema"]] == [dr.format_mac(MOCK_MAC)]
    assert "99:99:99:99:99:99" not in data["description_placeholders"]["devices"]


async def test_fix_flow_without_entry_falls_back_to_confirm(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an issue whose entry no longer exists gets a confirm flow."""
    assert await async_setup_component(hass, "repairs", {})
    ir.async_create_issue(
        hass,
        DOMAIN,
        "missing_address_gone",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="missing_address",
        data={"entry_id": "nonexistent"},
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, "missing_address_gone")
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, data["flow_id"], json={})
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, "missing_address_gone")
