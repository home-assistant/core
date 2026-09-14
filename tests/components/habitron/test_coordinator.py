"""Tests for the Habitron coordinator.

The coordinator owns the connection and the whole model: it resolves the host,
builds the hub and bus models, registers the devices and drives both refreshes.
These tests cover that span -- the setup path, the poll path, and the identity
rules that only Home Assistant can apply.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import (
    Area,
    Diagnostic,
    HabitronConnectionError,
    HabitronError,
    HabitronTimeoutError,
    Module,
    Router,
    Sensor,
    SmartHub,
)
import pytest

from homeassistant.components.habitron.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.habitron.coordinator import HbtnCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import MOCK_HOST, MOCK_MAC, MOCK_UID, TYPE_SMART_CONTROLLER

from tests.common import MockConfigEntry

_COORD = "homeassistant.components.habitron.coordinator"


def _hub(**overrides) -> SmartHub:
    """A built hub as ``async_build_hub`` would return it."""
    values = {
        "uid": MOCK_UID,
        "lan_mac": MOCK_MAC,
        "macs": [MOCK_MAC],
        "platform": "Raspberry Pi 4 Model B",
        "version": "5.1.0",
    }
    values.update(overrides)
    return SmartHub(**values)


def _ready(hass: HomeAssistant, entry=None) -> HbtnCoordinator:
    """A coordinator in the state ``_async_setup`` leaves behind."""
    coord = HbtnCoordinator(hass, entry or MagicMock())
    coord._client = MagicMock()
    coord.hub = _hub()
    coord._uid_from_mac = True
    coord.host = MOCK_HOST
    return coord


@pytest.fixture
def mock_refresh():
    """Stub both refresh calls the poll makes."""
    with (
        patch(
            f"{_COORD}.async_refresh_system", new=AsyncMock(return_value=4711)
        ) as bus,
        patch(f"{_COORD}.async_refresh_hub", new=AsyncMock()) as host,
    ):
        yield bus, host


async def test_update_returns_the_status_crc(hass: HomeAssistant, mock_refresh) -> None:
    """The CRC is the change-detection key the coordinator hands back."""
    bus, host = mock_refresh
    coord = _ready(hass)
    assert await coord._async_update_data() == 4711
    bus.assert_awaited_once()
    host.assert_awaited_once()


async def test_update_feeds_the_previous_crc_back(
    hass: HomeAssistant, mock_refresh
) -> None:
    """An unchanged bus must be able to skip the module re-parse."""
    bus, _ = mock_refresh
    coord = _ready(hass)
    await coord._async_update_data()
    await coord._async_update_data()
    assert bus.await_args.kwargs["last_crc"] == 4711


@pytest.mark.parametrize(
    ("side_effect", "expected_key"),
    [
        (TimeoutError("hub silent"), "update_timeout"),
        (HabitronTimeoutError("no response"), "update_timeout"),
        (OSError("dns down"), "update_network_error"),
        (HabitronConnectionError("bus down"), "update_network_error"),
    ],
)
async def test_update_translates_poll_failures(
    hass: HomeAssistant,
    mock_refresh,
    side_effect: Exception,
    expected_key: str,
) -> None:
    """A failed poll flips every entity unavailable with a translated reason."""
    bus, _ = mock_refresh
    bus.side_effect = side_effect
    coord = _ready(hass)
    with pytest.raises(UpdateFailed) as exc_info:
        await coord._async_update_data()
    assert exc_info.value.translation_key == expected_key


@pytest.mark.parametrize(
    "raised",
    [HabitronError("protocol glitch"), OSError("socket gone"), TimeoutError("slow")],
)
async def test_host_readings_never_fail_the_tick(
    hass: HomeAssistant, mock_refresh, raised: Exception
) -> None:
    """Host readings are non-essential.

    They are polled outside the guarded bus refresh, so a hiccup there must not
    mark *every* entity of the entry unavailable.
    """
    _, host = mock_refresh
    host.side_effect = raised
    coord = _ready(hass)
    assert await coord._async_update_data() == 4711


async def test_router_system_error_raises_and_clears_a_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_refresh,
) -> None:
    """An active fault is ERROR severity and names the hub.

    The name matters for a multi-hub install: the issue has to say which one.
    """
    entry = MagicMock()
    entry.title = "Living room hub"
    coord = _ready(hass, entry)
    coord.router = Router(uid="rt_1", sys_ok=False)

    await coord._async_update_data()
    issue = issue_registry.async_get_issue(DOMAIN, "router_system_error_rt_1")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"name": "Living room hub"}

    coord.router.sys_ok = True
    await coord._async_update_data()
    assert issue_registry.async_get_issue(DOMAIN, "router_system_error_rt_1") is None


async def test_router_issue_is_cleared_on_unload(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_refresh,
) -> None:
    """Without this an entry removed while faulty leaves a stale warning.

    No later tick can clear it -- the coordinator is gone.
    """
    coord = _ready(hass)
    coord.router = Router(uid="rt_1", sys_ok=False)
    await coord._async_update_data()
    assert issue_registry.async_get_issue(DOMAIN, "router_system_error_rt_1")

    coord.async_clear_router_issue()
    assert issue_registry.async_get_issue(DOMAIN, "router_system_error_rt_1") is None


async def test_heartbeat_shape(hass: HomeAssistant) -> None:
    """Fixed interval, and no fan-out on an unchanged bus."""
    coord = HbtnCoordinator(hass, MagicMock())
    assert coord.update_interval == SCAN_INTERVAL
    assert coord.always_update is False


@pytest.mark.parametrize(
    ("side_effect", "expected_key"),
    [
        (TimeoutError("silent"), "connect_timeout"),
        (HabitronTimeoutError("silent"), "connect_timeout"),
        (ConnectionRefusedError("refused"), "connect_refused"),
        (OSError("dns down"), "connect_error"),
        (HabitronConnectionError("protocol glitch"), "connect_error"),
    ],
)
async def test_setup_translates_connection_errors(
    hass: HomeAssistant,
    side_effect: Exception,
    expected_key: str,
) -> None:
    """A setup-phase failure becomes a *translated* ConfigEntryNotReady.

    Without translating here the first refresh would log the raw error as
    unexpected and surface a generic, untranslated ConfigEntryNotReady.
    """
    coord = HbtnCoordinator(hass, MagicMock())
    with (
        patch.object(
            HbtnCoordinator,
            "_async_connect_and_build",
            new=AsyncMock(side_effect=side_effect),
        ),
        pytest.raises(ConfigEntryNotReady) as exc_info,
    ):
        await coord._async_setup()
    assert exc_info.value.translation_key == expected_key


async def test_setup_does_not_retry_a_duplicate_hub(hass: HomeAssistant) -> None:
    """``ConfigEntryError`` must pass through ``_async_setup`` untouched.

    A second entry for a hub another entry already owns is not transient, so
    turning it into ConfigEntryNotReady would retry it forever.
    """
    coord = HbtnCoordinator(hass, MagicMock())
    with (
        patch.object(
            HbtnCoordinator,
            "_async_connect_and_build",
            new=AsyncMock(side_effect=ConfigEntryError("duplicate")),
        ),
        pytest.raises(ConfigEntryError),
    ):
        await coord._async_setup()


@pytest.mark.parametrize(
    ("configured", "expected", "resolver"),
    [
        (MOCK_HOST, MOCK_HOST, None),
        ("local", "192.168.1.10", "get_own_ip"),
        ("smarthub.local", MOCK_HOST, "get_host_ip"),
    ],
    ids=["literal-ip", "local-sentinel", "hostname"],
)
async def test_host_resolution(
    hass: HomeAssistant, configured: str, expected: str, resolver: str | None
) -> None:
    """A literal address is used as-is; anything else is resolved.

    ``get_own_ip`` blocks, so it goes to the executor; ``get_host_ip`` resolves
    with async DNS and must be awaited directly -- handing it to the executor
    would only build the coroutine and never run it.
    """
    entry = MagicMock()
    entry.data = {"host": configured}
    coord = HbtnCoordinator(hass, entry)
    if resolver == "get_own_ip":
        with patch(f"{_COORD}.get_own_ip", return_value=expected):
            assert await coord._async_resolve_host() == expected
    elif resolver == "get_host_ip":
        with patch(f"{_COORD}.get_host_ip", new=AsyncMock(return_value=expected)):
            assert await coord._async_resolve_host() == expected
    else:
        assert await coord._async_resolve_host() == expected


async def test_client_is_refused_before_setup(hass: HomeAssistant) -> None:
    """Touching the wire before setup is a programming error, not a retry."""
    coord = HbtnCoordinator(hass, MagicMock())
    with pytest.raises(RuntimeError, match="not connected"):
        _ = coord.client


async def test_close_releases_the_client(hass: HomeAssistant) -> None:
    """Unload drops the client so it can close any probe socket it holds."""
    coord = HbtnCoordinator(hass, MagicMock())
    client = MagicMock()
    client.close = AsyncMock()
    coord._client = client

    await coord.async_close()
    client.close.assert_awaited_once()
    # Idempotent: a second unload must not explode on the dropped reference.
    await coord.async_close()
    client.close.assert_awaited_once()


async def test_uid_is_the_hubs_own_address(hass: HomeAssistant) -> None:
    """The hub's own LAN address is the identity when it reports one."""
    coord = HbtnCoordinator(hass, MagicMock())
    coord.hub = _hub()
    coord._resolve_uid()
    assert coord.uid == MOCK_UID
    assert coord.has_mac_uid is True


async def test_uid_falls_back_to_the_entry(hass: HomeAssistant) -> None:
    """A hub reporting no usable address still needs one identity.

    Carrying an empty uid into the registry would give every device of every
    such installation the same blank identifier.
    """
    entry = MagicMock()
    entry.unique_id = None
    entry.entry_id = "01JENTRY"
    coord = HbtnCoordinator(hass, entry)
    coord.hub = _hub(uid="", lan_mac="")
    coord._resolve_uid()
    assert coord.uid == "01JENTRY"
    assert coord.has_mac_uid is False
    # Written onto the hub itself: the hub's entities read their device
    # identifier off that object, so a second copy could disagree with it.
    assert coord.hub.uid == "01JENTRY"


async def test_duplicate_hub_is_refused_before_the_registry_is_touched(
    hass: HomeAssistant,
) -> None:
    """Another entry already owns this hub, so its devices are keyed by this uid.

    Going on would attach a second, unusable entry to them.
    """
    existing = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_UID)
    existing.add_to_hass(hass)

    entry = MagicMock()
    entry.unique_id = "some-older-id"
    coord = HbtnCoordinator(hass, entry)
    coord.hub = _hub()
    with pytest.raises(ConfigEntryError) as exc_info:
        coord._resolve_uid()
    assert exc_info.value.translation_key == "duplicate_hub"


@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        # Stored relative: the frontend resolves ``homeassistant://`` against
        # whatever address the viewer is on, and ``configuration_url`` is
        # stored once -- a resolved address could only ever match either the
        # local network or a remote URL, never both.
        ("habitron_smarthub", "homeassistant://habitron_smarthub/ingress?index=%2Fhub"),
        # A standalone hub serves its own UI, and that address we do know.
        ("", f"http://{MOCK_HOST}:7780/hub"),
    ],
    ids=["add-on", "standalone"],
)
async def test_device_links_follow_the_deployment(
    hass: HomeAssistant, slug: str, expected: str
) -> None:
    """An add-on hub is reached through Home Assistant, a standalone one direct."""
    coord = _ready(hass)
    coord.hub = _hub(slug=slug)
    coord.base_url = coord._resolve_base_url()
    assert coord._conf_url("/hub") == expected


async def test_device_links_are_dropped_without_an_address(
    hass: HomeAssistant,
) -> None:
    """Nothing was resolved yet, so there is no page to point at."""
    coord = _ready(hass)
    coord.host = ""
    assert coord._conf_url("/hub") is None


async def test_build_registers_the_device_tree(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Hub, router and modules land in the registry, linked hub -> router -> module.

    The link goes through ``via_device_id`` rather than the deprecated
    ``via_device``, and the hub registers *every* address it reports so a
    discovery that saw the other interface still matches it.
    """
    mock_config_entry.add_to_hass(hass)
    router = Router(
        uid="rt_1",
        id=100,
        name="Router",
        version="1.0",
        serial="HBT-1",
        areas=[Area(nmbr=1, name="Living")],
        modules=[
            Module(
                uid="mod_1",
                addr=101,
                typ=TYPE_SMART_CONTROLLER,
                name="Module 1",
                mod_type="Smart Controller",
                area=1,
            )
        ],
    )

    client = MagicMock()
    client.connect = AsyncMock()
    client.reinit_hub = AsyncMock()
    client.send_devregid = AsyncMock()

    coord = HbtnCoordinator(hass, mock_config_entry)
    with (
        patch(f"{_COORD}.HabitronClient", return_value=client),
        patch(f"{_COORD}.async_build_hub", new=AsyncMock(return_value=_hub())),
        patch(f"{_COORD}.async_build_system", new=AsyncMock(return_value=router)),
    ):
        await coord._async_connect_and_build()

    entry_id = mock_config_entry.entry_id
    hub_dev = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_UID), entry_id
    )
    rt_dev = device_registry.async_get_device_by_identifier((DOMAIN, "rt_1"), entry_id)
    mod_dev = device_registry.async_get_device_by_identifier(
        (DOMAIN, "mod_1"), entry_id
    )
    assert hub_dev and rt_dev and mod_dev
    assert hub_dev.connections == {(dr.CONNECTION_NETWORK_MAC, dr.format_mac(MOCK_MAC))}
    assert rt_dev.via_device_id == hub_dev.id
    assert mod_dev.via_device_id == rt_dev.id
    # The bus area seeds the module's area on creation only.
    assert mod_dev.area_id is not None

    # The hub's event server is stopped for the build and always restored.
    assert [call.args[0] for call in client.reinit_hub.await_args_list] == [0, 1]
    # Every device gets its registry id pushed back to the bus member.
    assert client.send_devregid.await_count == 2


async def test_event_server_is_restored_even_when_the_build_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Otherwise the hub stays stopped while Home Assistant retries the setup."""
    mock_config_entry.add_to_hass(hass)
    client = MagicMock()
    client.connect = AsyncMock()
    client.reinit_hub = AsyncMock()

    coord = HbtnCoordinator(hass, mock_config_entry)
    with (
        patch(f"{_COORD}.HabitronClient", return_value=client),
        patch(f"{_COORD}.async_build_hub", new=AsyncMock(return_value=_hub())),
        patch(
            f"{_COORD}.async_build_system",
            new=AsyncMock(side_effect=HabitronError("truncated")),
        ),
        pytest.raises(HabitronError),
    ):
        await coord._async_connect_and_build()

    assert [call.args[0] for call in client.reinit_hub.await_args_list] == [0, 1]


async def test_host_readings_reach_the_hub_members(hass: HomeAssistant) -> None:
    """The library writes the readings; the coordinator only drives the poll."""
    coord = _ready(hass)
    coord.hub.diags = [Diagnostic(name="CPU load", nmbr=0, type=10)]
    coord.hub.sensors = [Sensor(name="Memory usage", nmbr=0, type=2)]

    async def _apply(client, hub, *, hbtn_version):
        hub.diags[0].value = 12.0
        hub.host_valid = True

    with patch(f"{_COORD}.async_refresh_hub", new=_apply):
        await coord._async_update_host()

    assert coord.hub.diags[0].value == 12.0
    assert coord.hub.host_valid is True


async def test_integration_version_is_reported_to_the_hub(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The hub is told which integration version is talking to it.

    Core manifests carry no version, so this stays at the 0.0.0 default there;
    the same code running as a custom integration has one and reports it.
    """
    mock_config_entry.add_to_hass(hass)
    client = MagicMock()
    client.connect = AsyncMock()
    client.reinit_hub = AsyncMock()
    client.send_devregid = AsyncMock()

    coord = HbtnCoordinator(hass, mock_config_entry)
    with (
        patch(f"{_COORD}.HabitronClient", return_value=client),
        patch(f"{_COORD}.async_build_hub", new=AsyncMock(return_value=_hub())),
        patch(f"{_COORD}.async_build_system", new=AsyncMock(return_value=Router())),
        patch(
            f"{_COORD}.async_get_integration",
            new=AsyncMock(return_value=MagicMock(version="3.2.5")),
        ),
    ):
        await coord._async_connect_and_build()

    assert coord._hbtn_version == "3.2.5"
