"""Tests for the Habitron SmartHub class."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from habitron_client import (
    Diagnostic,
    HabitronClient,
    HabitronError,
    HabitronProtocolError,
    HostDiagnostics,
    Router,
    Sensor,
)
import pytest

from homeassistant.components.habitron.const import DOMAIN
from homeassistant.components.habitron.smart_hub import SmartHub
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_CONFIG_DATA, MOCK_CONFIG_OPTIONS, MOCK_HOST, MOCK_NAME, MOCK_UID

from tests.common import MockConfigEntry


@pytest.fixture
def smart_hub_stub() -> SmartHub:
    """Build a SmartHub with the comm transport stubbed out."""
    comm = MagicMock()
    comm.com_ip = MOCK_HOST
    comm.com_port = 7777
    comm.com_mac = "AA:BB:CC:DD:EE:FF"
    comm.com_macs = ["AA:BB:CC:DD:EE:FF"]
    comm.com_version = "9.9.9"
    comm.com_hwtype = "Raspberry Pi 4"
    comm.is_addon = False
    comm.slugname = ""
    comm.async_setup = AsyncMock()
    comm.async_close = AsyncMock()
    comm.get_smhub_info = AsyncMock()
    comm.get_host_diagnostics = AsyncMock()
    comm.reinit_hub = AsyncMock()
    comm.send_network_info = AsyncMock()
    comm.send_devregid = AsyncMock()
    comm.set_router = MagicMock()

    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    config = MagicMock()
    config.title = "Habitron"
    config.entry_id = "entry-id"
    config.data = {}
    return SmartHub(hass, config, comm)


def _smhub_info(slug: str = "", mac: str = "AA:BB:CC:DD:EE:FF") -> dict:
    """A realistic SmartHub info payload as the client returns it."""
    return {
        "software": {"version": "9.9.9", "slug": slug},
        "hardware": {
            "platform": {"type": "Other"},
            "network": {
                "ip": MOCK_HOST,
                "host": "smarthub",
                "lan mac": mac,
            },
        },
    }


@pytest.mark.parametrize(
    ("slug", "expected_conf_url"),
    [
        # External/standalone hub: literal "none" slug -> direct base URL.
        ("none", f"http://{MOCK_HOST}:7780/hub"),
        # Add-on hub: it reports its ingress slug -> ingress base URL.
        (
            "habitron_smarthub",
            f"http://{MOCK_HOST}:8123/habitron_smarthub/ingress?index=/hub",
        ),
    ],
)
@pytest.mark.parametrize(
    "reported_mac",
    # The uid derived from this becomes the device identifier and prefixes
    # every entity unique id, so all three spellings have to land on one uid --
    # a hub switching notation after a firmware update must not produce a
    # second set of devices and entities. The expected form is lower case
    # because the custom (HACS) integration writes it that way into this very
    # registry; diverging would orphan a migrating installation's history.
    ["AA:BB:CC:DD:EE:FF", "aa-bb-cc-dd-ee-ff", "aabbccddeeff"],
)
async def test_setup_registers_hub_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    slug: str,
    expected_conf_url: str,
    reported_mac: str,
) -> None:
    """Full config-entry setup registers the hub device in the registry.

    Drives the public path (config entry -> SmartHub.async_setup -> device
    registry); only the ``habitron_client`` boundary and the bus-model build are
    mocked, so the real wiring (addon vs standalone base URL included) runs.
    The add-on vs standalone base URL is driven by the target hub's reported
    slug, not this HA's supervisor token.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
    )
    entry.add_to_hass(hass)

    client = AsyncMock(spec=HabitronClient)
    client.host = MOCK_HOST
    client.get_smhub_info = AsyncMock(return_value=_smhub_info(slug, reported_mac))
    router = Router(uid="rt_1")
    router.modules = []
    router.areas = []

    with (
        patch(
            "homeassistant.components.habitron.communicate.HabitronClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.habitron.communicate.get_own_ip",
            return_value="192.168.1.10",
        ),
        patch(
            "homeassistant.components.habitron.communicate.get_host_ip",
            new=AsyncMock(return_value=MOCK_HOST),
        ),
        patch(
            "homeassistant.components.habitron.smart_hub.async_build_system",
            new=AsyncMock(return_value=router),
        ),
        patch(
            "homeassistant.components.habitron.coordinator."
            "HbtnCoordinator._async_update_data",
            new=AsyncMock(return_value=0),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, MOCK_UID)})
    assert device is not None
    assert device.manufacturer == "Habitron GmbH"
    assert device.sw_version == "9.9.9"
    # The hardware platform is the model; there is no separate hw revision.
    assert device.model == "Other"
    assert device.hw_version is None
    assert device.configuration_url == expected_conf_url


def test_smhub_public_properties(smart_hub_stub: SmartHub) -> None:
    """The SmartHub exposes its version, hardware type and configured name."""
    smart_hub_stub._version = "7.7.7"
    smart_hub_stub._type = "Raspberry Pi 5"
    smart_hub_stub._name = "Living room hub"
    assert smart_hub_stub.smhub_version == "7.7.7"
    assert smart_hub_stub.smhub_type == "Raspberry Pi 5"
    assert smart_hub_stub.smhub_name == "Living room hub"


@pytest.mark.parametrize(
    "raised",
    [
        HabitronError("bus"),
        # The library raises this for a payload it cannot read.
        HabitronProtocolError("cpu.load is not a number"),
        OSError("no route"),
        TimeoutError(),
    ],
)
async def test_update_swallows_transport_errors(
    smart_hub_stub: SmartHub, raised: Exception
) -> None:
    """A failing diagnostics read never reaches the coordinator.

    ``update()`` runs outside the coordinator's guarded bus refresh, so a socket
    error or timeout would otherwise fail the whole tick and mark every entity
    unavailable -- for readings the contract calls non-essential.
    """
    smart_hub_stub.diags = [Diagnostic(name="Status", nmbr=0, type=1)]
    smart_hub_stub.comm.get_host_diagnostics.side_effect = raised

    await smart_hub_stub.update()

    assert smart_hub_stub.host_diags_valid is False


async def test_update_swallows_habitron_error(smart_hub_stub: SmartHub) -> None:
    """A library error during the diagnostics read is non-fatal (swallowed).

    Host diagnostics are decoupled from the bus status: a dropped/bad response
    must not fail the coordinator tick or abort setup, so update() catches the
    library error and keeps the last values.
    """
    smart_hub_stub.comm.get_host_diagnostics.side_effect = HabitronError("boom")
    smart_hub_stub.diags = [Diagnostic(name="Status", nmbr=0, type=1)]
    await smart_hub_stub.update()  # must not raise
    smart_hub_stub.comm.get_host_diagnostics.assert_awaited_once()
    # Nothing was read, so the host readings must stay unknown rather than
    # publishing the zero defaults as if they were measurements.
    assert smart_hub_stub.host_diags_valid is False


async def test_setup_without_a_mac_keeps_the_entry_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A hub reporting no MAC does not get an empty identifier.

    The config flow accepts that case and keys the entry by its host, so setup
    has to carry that id instead of prefixing every device and entity with an
    empty string -- and it must not register a blank MAC connection.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="habitron_192.168.1.50",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
    )
    entry.add_to_hass(hass)

    client = AsyncMock(spec=HabitronClient)
    client.host = MOCK_HOST
    client.get_smhub_info = AsyncMock(return_value=_smhub_info("none", ""))
    router = Router(uid="rt_1")
    with (
        patch(
            "homeassistant.components.habitron.communicate.HabitronClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.habitron.smart_hub.async_build_system",
            new=AsyncMock(return_value=router),
        ),
        patch(
            "homeassistant.components.habitron.coordinator."
            "HbtnCoordinator._async_update_data",
            new=AsyncMock(return_value=0),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "habitron_192.168.1.50")}
    )
    assert device is not None
    assert device.connections == set()


async def test_setup_registers_every_interface_mac(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Both interfaces become connections, but only the LAN MAC is the identity.

    The hub answers over whichever interface is up, so a discovery that saw the
    other one has to match this same device rather than create a second.
    """
    info = _smhub_info("none")
    info["hardware"]["network"]["wlan mac"] = "11:22:33:44:55:66"
    info["hardware"]["network"]["mac"] = "11:22:33:44:55:66"

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="aabbccddeeff",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
    )
    entry.add_to_hass(hass)

    client = AsyncMock(spec=HabitronClient)
    client.host = MOCK_HOST
    client.get_smhub_info = AsyncMock(return_value=info)
    router = Router(uid="rt_1")
    with (
        patch(
            "homeassistant.components.habitron.communicate.HabitronClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.habitron.smart_hub.async_build_system",
            new=AsyncMock(return_value=router),
        ),
        patch(
            "homeassistant.components.habitron.coordinator."
            "HbtnCoordinator._async_update_data",
            new=AsyncMock(return_value=0),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, "aabbccddeeff")})
    assert device is not None
    assert device.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff"),
        (dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:66"),
    }


async def test_update_short_circuits_when_no_diags(smart_hub_stub: SmartHub) -> None:
    """update() skips the query entirely when self.diags is empty.

    Non-Raspberry-Pi hubs have no host diagnostics, so it must not fetch and
    discard a SmartHub update on every tick.
    """
    smart_hub_stub.diags = []
    await smart_hub_stub.update()
    smart_hub_stub.comm.get_host_diagnostics.assert_not_awaited()


async def test_update_writes_diag_sensor_and_log_levels(
    smart_hub_stub: SmartHub,
) -> None:
    """A fully-populated info dict is parsed into the descriptor lists."""
    smart_hub_stub.comm.get_host_diagnostics.return_value = HostDiagnostics(
        cpu_frequency=1500,
        cpu_load=12,
        cpu_temperature=55.5,
        memory_usage=60,
        disk_usage=30,
        log_level_console=3,
        log_level_file=4,
    )
    smart_hub_stub.diags = [
        Diagnostic(name="CPU Frequency", nmbr=0, type=10),
        Diagnostic(name="CPU load", nmbr=1, type=10),
        Diagnostic(name="CPU Temperature", nmbr=2, type=10),
    ]
    smart_hub_stub.sensors = [
        Sensor(name="Memory usage", nmbr=0, type=2, value=0),
        Sensor(name="Disk usage", nmbr=1, type=2, value=0),
    ]
    smart_hub_stub.loglvl = [
        Sensor(name="Logging level console", nmbr=0, type=2, value=0),
        Sensor(name="Logging level file", nmbr=1, type=2, value=0),
    ]

    await smart_hub_stub.update()

    assert smart_hub_stub.diags[0].value == 1500.0
    assert smart_hub_stub.diags[1].value == 12.0
    assert smart_hub_stub.diags[2].value == 55.5
    assert smart_hub_stub.sensors[0].value == 60.0
    assert smart_hub_stub.sensors[1].value == 30.0
    assert smart_hub_stub.loglvl[0].value == 3
    assert smart_hub_stub.loglvl[1].value == 4
    assert smart_hub_stub.host_diags_valid is True


async def test_update_notifies_all_members_on_first_success(
    smart_hub_stub: SmartHub,
) -> None:
    """The first successful read notifies every member, even unchanged ones.

    When the setup-time reads failed, the entities report ``unknown``. A later
    successful read must publish *all* host readings, including members whose
    value happens to equal the placeholder they were seeded with -- those do
    not notify on their own, and with an otherwise idle bus their entities
    would stay ``unknown`` indefinitely.
    """
    smart_hub_stub.comm.get_host_diagnostics.return_value = HostDiagnostics(
        cpu_frequency=1500,
        cpu_load=12,
        cpu_temperature=55.5,
        memory_usage=60,
        disk_usage=30,
        log_level_console=0,
        log_level_file=0,
    )
    # Seed every member with the value the read will return, so no _set() call
    # sees a change and none of them notifies by itself.
    smart_hub_stub.diags = [
        Diagnostic(name="CPU Frequency", nmbr=0, type=10, value=1500.0),
        Diagnostic(name="CPU load", nmbr=1, type=10, value=12.0),
        Diagnostic(name="CPU Temperature", nmbr=2, type=10, value=55.5),
    ]
    smart_hub_stub.sensors = [
        Sensor(name="Memory usage", nmbr=0, type=2, value=60.0),
        Sensor(name="Disk usage", nmbr=1, type=2, value=30.0),
    ]
    smart_hub_stub.loglvl = [
        Sensor(name="Logging level console", nmbr=0, type=2, value=0),
        Sensor(name="Logging level file", nmbr=1, type=2, value=0),
    ]
    members = [
        *smart_hub_stub.diags,
        *smart_hub_stub.sensors,
        *smart_hub_stub.loglvl,
    ]
    for member in members:
        member.notify = Mock()
    smart_hub_stub.host_diags_valid = False

    await smart_hub_stub.update()

    assert smart_hub_stub.host_diags_valid is True
    for member in members:
        assert member.notify.call_count == 1

    # A subsequent unchanged read must not re-notify: the entities are already
    # showing these values.
    for member in members:
        member.notify.reset_mock()

    await smart_hub_stub.update()

    for member in members:
        member.notify.assert_not_called()


async def test_recovery_notifies_every_member_exactly_once(
    smart_hub_stub: SmartHub,
) -> None:
    """On recovery a changed member is not written twice.

    ``_set`` already notifies what it changed, so the catch-up loop must cover
    only the members that still match their placeholder -- otherwise every
    normal reading produces a duplicate entity state write.
    """
    smart_hub_stub.comm.get_host_diagnostics.return_value = HostDiagnostics(
        cpu_frequency=1500,
        cpu_load=12,
        cpu_temperature=55.5,
        memory_usage=60,
        disk_usage=30,
        log_level_console=0,
        log_level_file=0,
    )
    # Mixed on purpose: the CPU members change, the rest already match what the
    # read returns.
    smart_hub_stub.diags = [
        Diagnostic(name="CPU Frequency", nmbr=0, type=10, value=0.0),
        Diagnostic(name="CPU load", nmbr=1, type=10, value=0.0),
        Diagnostic(name="CPU Temperature", nmbr=2, type=10, value=0.0),
    ]
    smart_hub_stub.sensors = [
        Sensor(name="Memory usage", nmbr=0, type=2, value=60.0),
        Sensor(name="Disk usage", nmbr=1, type=2, value=30.0),
    ]
    smart_hub_stub.loglvl = [
        Sensor(name="Logging level console", nmbr=0, type=2, value=0),
        Sensor(name="Logging level file", nmbr=1, type=2, value=0),
    ]
    members = [
        *smart_hub_stub.diags,
        *smart_hub_stub.sensors,
        *smart_hub_stub.loglvl,
    ]
    for member in members:
        member.notify = Mock()
    smart_hub_stub.host_diags_valid = False

    await smart_hub_stub.update()

    for member in members:
        assert member.notify.call_count == 1


async def test_async_close_delegates_to_comm(
    smart_hub_stub: SmartHub,
) -> None:
    """async_close hands off to comm.async_close to release the bus client."""
    await smart_hub_stub.async_close()
    smart_hub_stub.comm.async_close.assert_awaited()
