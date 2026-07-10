"""Tests for the Habitron SmartHub class."""

from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import Diagnostic, HabitronClient, HabitronError, Router, Sensor
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
    comm.com_version = "9.9.9"
    comm.com_hwtype = "Raspberry Pi 4"
    comm.is_addon = False
    comm.slugname = ""
    comm.async_setup = AsyncMock()
    comm.async_close = AsyncMock()
    comm.get_smhub_info = AsyncMock()
    comm.get_smhub_update = AsyncMock()
    comm.reinit_hub = AsyncMock()
    comm.send_network_info = AsyncMock()
    comm.send_devregid = AsyncMock()
    comm.set_router = MagicMock()

    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    config = MagicMock()
    config.title = "Habitron"
    config.entry_id = "entry-id"
    config.data = {"websock_token": "tok"}
    return SmartHub(hass, config, comm)


def _smhub_info(slug: str = "") -> dict:
    """A realistic SmartHub info payload as the client returns it."""
    return {
        "software": {"version": "9.9.9", "slug": slug},
        "hardware": {
            "platform": {"type": "Other"},
            "network": {
                "ip": MOCK_HOST,
                "host": "smarthub",
                "lan mac": "AA:BB:CC:DD:EE:FF",
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
async def test_setup_registers_hub_device(
    hass: HomeAssistant,
    slug: str,
    expected_conf_url: str,
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
    client.get_smhub_info = AsyncMock(return_value=_smhub_info(slug))
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
            return_value=MOCK_HOST,
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

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "AABBCCDDEEFF")})
    assert device is not None
    assert device.manufacturer == "Habitron GmbH"
    assert device.sw_version == "9.9.9"
    assert device.configuration_url == expected_conf_url


def test_smhub_public_properties(smart_hub_stub: SmartHub) -> None:
    """The SmartHub exposes its version, hardware type and configured name."""
    smart_hub_stub._version = "7.7.7"
    smart_hub_stub._type = "Raspberry Pi 5"
    smart_hub_stub._name = "Living room hub"
    assert smart_hub_stub.smhub_version == "7.7.7"
    assert smart_hub_stub.smhub_type == "Raspberry Pi 5"
    assert smart_hub_stub.smhub_name == "Living room hub"


async def test_update_short_circuits_when_no_info(smart_hub_stub: SmartHub) -> None:
    """update() returns early when get_smhub_update yields no data."""
    smart_hub_stub.comm.get_smhub_update.return_value = None
    smart_hub_stub.diags = []
    await smart_hub_stub.update()
    smart_hub_stub.comm.get_smhub_update.assert_awaited_once()


async def test_update_swallows_habitron_error(smart_hub_stub: SmartHub) -> None:
    """A library error during the diagnostics read is non-fatal (swallowed).

    Host diagnostics are decoupled from the bus status: a dropped/bad response
    must not fail the coordinator tick or abort setup, so update() catches the
    library error and keeps the last values.
    """
    smart_hub_stub.comm.get_smhub_update.side_effect = HabitronError("boom")
    await smart_hub_stub.update()  # must not raise
    smart_hub_stub.comm.get_smhub_update.assert_awaited_once()


async def test_update_short_circuits_when_no_diags(smart_hub_stub: SmartHub) -> None:
    """update() returns early when self.diags is still empty."""
    smart_hub_stub.comm.get_smhub_update.return_value = {"hardware": {}}
    smart_hub_stub.diags = []
    await smart_hub_stub.update()  # no exception, just early return


async def test_update_writes_diag_sensor_and_log_levels(
    smart_hub_stub: SmartHub,
) -> None:
    """A fully-populated info dict is parsed into the descriptor lists."""
    smart_hub_stub.comm.get_smhub_update.return_value = {
        "hardware": {
            "cpu": {
                "frequency current": "1500MHz",
                "load": "12%",
                "temperature": "55.5°C",
            },
            "memory": {"percent": "60%"},
            "disk": {"percent": "30%"},
        },
        "software": {"loglevel": {"console": "3", "file": "4"}},
    }
    smart_hub_stub.diags = [
        Diagnostic(name="CPU Frequency", nmbr=0, type=10),
        Diagnostic(name="CPU load", nmbr=1, type=10),
        Diagnostic(name="CPU Temperature", nmbr=2, type=10),
    ]
    smart_hub_stub.sensors = [
        Sensor(name="Memory free", nmbr=0, type=2, value=0),
        Sensor(name="Disk free", nmbr=1, type=2, value=0),
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


async def test_async_close_delegates_to_comm(
    smart_hub_stub: SmartHub,
) -> None:
    """async_close hands off to comm.async_close to release the bus client."""
    await smart_hub_stub.async_close()
    smart_hub_stub.comm.async_close.assert_awaited()
