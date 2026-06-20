"""Tests for the Habitron SmartHub class."""

from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import HabitronError, Router
import pytest

from homeassistant.components.habitron.smart_hub import LoggingLevels, SmartHub
from homeassistant.components.habitron.system_health import (
    async_register,
    system_health_info,
)

from .const import MOCK_HOST


def test_logging_levels_enum_values() -> None:
    """LoggingLevels exposes the documented int values for each named level."""
    assert LoggingLevels.notset.value == 0
    assert LoggingLevels.debug.value == 1
    assert LoggingLevels.info.value == 2
    assert LoggingLevels.warning.value == 3
    assert LoggingLevels.error.value == 4
    assert LoggingLevels.critical.value == 5


@pytest.fixture
def smart_hub_stub() -> SmartHub:
    """Build a SmartHub with the heavy dependencies stubbed out."""
    with (
        patch("homeassistant.components.habitron.smart_hub.hbtn_com") as mock_com,
        patch("homeassistant.components.habitron.smart_hub.HbtnCoordinator"),
    ):
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
        comm.get_smhub_version = AsyncMock()
        comm.reinit_hub = AsyncMock()
        comm.send_network_info = AsyncMock()
        comm.send_devregid = AsyncMock()
        comm.set_router = MagicMock()
        comm.hub_restart = AsyncMock()
        comm.hub_reboot = AsyncMock()
        mock_com.return_value = comm

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        config = MagicMock()
        config.title = "Habitron"
        config.entry_id = "entry-id"
        config.data = {"websock_token": "tok"}
        hub = SmartHub(hass, config)
    return hub  # noqa: RET504


def test_smhub_init_sets_placeholder_uid_and_owns_router(
    smart_hub_stub: SmartHub,
) -> None:
    """__init__ leaves uid as ``pending`` until async_setup runs."""
    assert smart_hub_stub.uid == "pending"
    assert smart_hub_stub._mac == "00:00:00:00:00:00"
    assert smart_hub_stub.online is True
    assert smart_hub_stub.router is not None
    assert smart_hub_stub.addon_slug == ""
    assert smart_hub_stub.base_url == ""


def test_smhub_version_property(smart_hub_stub: SmartHub) -> None:
    """smhub_version returns the cached version field."""
    smart_hub_stub._version = "1.2.3"
    assert smart_hub_stub.smhub_version == "1.2.3"


async def test_smhub_async_setup_populates_fields_and_diagnostics(
    smart_hub_stub: SmartHub,
) -> None:
    """async_setup populates uid, base_url, registers the device and diagnostics."""
    smart_hub_stub.comm.get_smhub_update.return_value = None

    with (
        patch("homeassistant.components.habitron.smart_hub.dr") as mock_dr,
        patch("homeassistant.components.habitron.smart_hub.ar"),
        patch(
            "homeassistant.components.habitron.smart_hub.async_build_system",
            new=AsyncMock(return_value=Router()),
        ),
    ):
        mock_dr.async_get.return_value = MagicMock()
        mock_dr.CONNECTION_NETWORK_MAC = "mac"
        await smart_hub_stub.async_setup()

    # uid is the colon-stripped MAC
    assert smart_hub_stub.uid == "AABBCCDDEEFF"
    # base_url uses port 7780 for non-addon installs
    assert smart_hub_stub.base_url.endswith(":7780")
    # Raspberry Pi branch fills three diags + two sensors + two log levels
    assert len(smart_hub_stub.diags) == 3
    assert len(smart_hub_stub.sensors) == 2
    assert len(smart_hub_stub.loglvl) == 2


async def test_smhub_async_setup_addon_branch_sets_ingress_base_url(
    smart_hub_stub: SmartHub,
) -> None:
    """When ``comm.is_addon`` is True, base_url points at the ingress endpoint."""
    smart_hub_stub.comm.is_addon = True
    smart_hub_stub.comm.slugname = "habitron_smarthub"
    smart_hub_stub.comm.com_hwtype = "Other"  # skip RPi diag setup

    with (
        patch("homeassistant.components.habitron.smart_hub.dr") as mock_dr,
        patch("homeassistant.components.habitron.smart_hub.ar"),
        patch(
            "homeassistant.components.habitron.smart_hub.async_build_system",
            new=AsyncMock(return_value=Router()),
        ),
    ):
        mock_dr.async_get.return_value = MagicMock()
        mock_dr.CONNECTION_NETWORK_MAC = "mac"
        await smart_hub_stub.async_setup()

    assert "habitron_smarthub/ingress?index=" in smart_hub_stub.base_url
    # Non-RPi branch leaves the diag/sensor/loglvl lists empty
    assert smart_hub_stub.diags == []
    assert smart_hub_stub.sensors == []
    assert smart_hub_stub.loglvl == []


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
    smart_hub_stub.diags = [MagicMock(), MagicMock(), MagicMock()]
    smart_hub_stub.sensors = [MagicMock(), MagicMock()]
    smart_hub_stub.loglvl = [MagicMock(), MagicMock()]

    await smart_hub_stub.update()

    assert smart_hub_stub.diags[0].value == 1500.0
    assert smart_hub_stub.diags[1].value == 12.0
    assert smart_hub_stub.diags[2].value == 55.5
    assert smart_hub_stub.sensors[0].value == 60.0
    assert smart_hub_stub.sensors[1].value == 30.0
    assert smart_hub_stub.loglvl[0].value == 3
    assert smart_hub_stub.loglvl[1].value == 4


async def test_async_update_delegates_to_update(
    smart_hub_stub: SmartHub,
) -> None:
    """async_update is now a thin awaiter around update() directly."""
    smart_hub_stub.comm.get_smhub_update.return_value = None
    smart_hub_stub.diags = []
    await smart_hub_stub.async_update()
    smart_hub_stub.comm.get_smhub_update.assert_awaited()


async def test_async_close_delegates_to_comm(
    smart_hub_stub: SmartHub,
) -> None:
    """async_close hands off to comm.async_close to tear down the persistent client."""
    await smart_hub_stub.async_close()
    smart_hub_stub.comm.async_close.assert_awaited()


async def test_get_version_strips_smartip_prefix(
    smart_hub_stub: SmartHub,
) -> None:
    """``get_version`` strips the leading SmartIP marker from the reply."""
    # ``get_version`` returns ver_string[9:] when the SmartIP prefix is
    # present — so the version payload sits at byte index 9.
    smart_hub_stub.comm.get_smhub_version = AsyncMock(
        return_value=b"SmartIP\x00\x001.2.3.4"
    )
    ver = await smart_hub_stub.get_version()
    assert ver == "1.2.3.4"


async def test_get_version_returns_zero_default_when_marker_missing(
    smart_hub_stub: SmartHub,
) -> None:
    """If the SmartIP marker is missing, ``get_version`` falls back to 0.0.0."""
    smart_hub_stub.comm.get_smhub_version = AsyncMock(return_value=b"garbled")
    ver = await smart_hub_stub.get_version()
    assert ver == "0.0.0"


async def test_restart_forwards_to_comm(smart_hub_stub: SmartHub) -> None:
    """``restart`` accepts a router id (forward-compat) but forwards a no-arg call."""
    await smart_hub_stub.restart(7)
    smart_hub_stub.comm.hub_restart.assert_awaited_with()


async def test_reboot_forwards_to_comm(smart_hub_stub: SmartHub) -> None:
    """reboot() forwards the call to ``comm.hub_reboot``."""
    await smart_hub_stub.reboot()
    smart_hub_stub.comm.hub_reboot.assert_awaited()


def test_async_register_forwards_system_health_info() -> None:
    """``async_register`` wires ``system_health_info`` into the registration helper."""

    hass = MagicMock()
    register = MagicMock()
    async_register(hass, register)
    register.async_register_info.assert_called_with(system_health_info)
