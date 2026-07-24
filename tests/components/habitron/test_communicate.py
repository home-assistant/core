"""Tests for the Habitron communicate (HbtnComm) layer (v2 thin transport)."""

from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import HabitronClient, HabitronTimeoutError, Router
import pytest

from homeassistant.components.habitron.communicate import HbtnComm


def _make_comm(host: str = "192.168.1.50") -> HbtnComm:
    """Build an HbtnComm with the client stubbed out."""
    hass = MagicMock()
    hass.data = {"integrations": {"habitron": MagicMock(manifest={"version": "9.9.9"})}}
    hass.async_add_executor_job = AsyncMock()
    config = MagicMock()
    config.data = {"habitron_host": host}
    comm = HbtnComm(hass, config)
    comm._client = AsyncMock(spec=HabitronClient)
    return comm


def test_init_with_valid_ipv4_uses_host_directly() -> None:
    """A valid IPv4 in config is stored as the active host."""
    comm = _make_comm("10.0.0.5")
    assert comm._host == "10.0.0.5"


def test_init_with_hostname_leaves_host_empty() -> None:
    """A non-IPv4 hostname produces an empty initial host (resolved later)."""
    assert _make_comm("my-hub.local")._host == ""


def test_is_valid_ipv4() -> None:
    """``is_valid_ipv4`` accepts valid IPv4 only."""
    comm = _make_comm()
    assert comm.is_valid_ipv4("192.168.1.1") is True
    assert comm.is_valid_ipv4("not-an-ip") is False


def test_property_accessors() -> None:
    """Public properties expose the cached fields."""
    comm = _make_comm("10.0.0.5")
    comm._mac = "AA:BB"
    comm._version = "1.2.3"
    assert comm.com_ip == "10.0.0.5"
    assert comm.com_mac == "AA:BB"
    assert comm.com_version == "1.2.3"
    assert comm.hbtn_version == "0.0.0"


def test_router_property_returns_own_router() -> None:
    """``router`` returns the comm's own router, set via set_router."""
    comm = _make_comm()
    assert isinstance(comm.router, Router)
    other = Router(uid="rt_y")
    comm.set_router(other)
    assert comm.router is other


async def test_async_system_update_suspended_returns_crc() -> None:
    """While suspended no refresh happens and the cached CRC is returned."""
    comm = _make_comm()
    comm.update_suspended = True
    comm.crc = 7
    with patch(
        "homeassistant.components.habitron.communicate.async_refresh_system",
        new=AsyncMock(),
    ) as refresh:
        assert await comm.async_system_update() == 7
        refresh.assert_not_called()


async def test_async_system_update_refreshes_and_returns_new_crc() -> None:
    """A normal tick refreshes the bus, returning the new CRC."""
    comm = _make_comm()
    with patch(
        "homeassistant.components.habitron.communicate.async_refresh_system",
        new=AsyncMock(return_value=99),
    ) as refresh:
        assert await comm.async_system_update() == 99
        refresh.assert_awaited()
        assert comm.crc == 99


async def test_get_smhub_info_populates_fields() -> None:
    """get_smhub_info fills mac/version/host fields from the validated info."""
    comm = _make_comm()
    info = {
        "software": {"version": "1.0", "slug": "habitron"},
        "hardware": {
            "platform": {"type": "Raspberry Pi 4"},
            "network": {"ip": "10.0.0.5", "host": "smarthub", "lan mac": "AA:BB"},
        },
    }
    comm._client.get_smhub_info = AsyncMock(return_value=info)
    out = await comm.get_smhub_info()
    assert out["software"]["version"] == "1.0"
    assert comm.com_version == "1.0"
    assert comm.com_mac == "AA:BB"
    assert comm.com_ip == "10.0.0.5"
    assert comm.slugname == "habitron"
    assert comm.is_addon is True


async def test_get_smhub_info_external_hub_has_none_slug() -> None:
    """A standalone hub reports the literal "none" slug, so is_addon is False."""
    comm = _make_comm()
    info = {
        "software": {"version": "1.0", "slug": "none"},
        "hardware": {
            "platform": {"type": "Raspberry Pi 4"},
            "network": {"ip": "10.0.0.5", "host": "smarthub", "lan mac": "AA:BB"},
        },
    }
    comm._client.get_smhub_info = AsyncMock(return_value=info)
    await comm.get_smhub_info()
    assert comm.slugname == ""
    assert comm.is_addon is False


async def test_async_setup_resolves_host_and_connects() -> None:
    """async_setup resolves a hostname and connects a fresh client.

    ``get_host_ip`` does its own async DNS, so it has to be awaited directly.
    Handing it to the executor would assign the *coroutine* to ``_host`` (never
    resolving it), so assert the stored host is the resolved string.
    """
    comm = _make_comm("my-hub.local")
    comm._client = None
    client = AsyncMock(spec=HabitronClient)
    with (
        patch(
            "homeassistant.components.habitron.communicate.get_host_ip",
            new=AsyncMock(return_value="10.0.0.9"),
        ),
        patch(
            "homeassistant.components.habitron.communicate.network.async_get_source_ip",
            new=AsyncMock(return_value="10.0.0.1"),
        ),
        patch(
            "homeassistant.components.habitron.communicate.HabitronClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.habitron.communicate.async_get_integration",
            new=AsyncMock(return_value=MagicMock(version="3.0.2")),
        ),
    ):
        await comm.async_setup()
    assert comm._host == "10.0.0.9"
    assert isinstance(comm._host, str)
    assert comm.hbtn_version == "3.0.2"
    client.connect.assert_awaited()


def test_client_property_raises_when_not_connected() -> None:
    """Accessing ``client`` before async_setup is a hard error."""
    comm = _make_comm()
    comm._client = None
    with pytest.raises(RuntimeError, match="not connected"):
        _ = comm.client


async def test_async_setup_local_host_uses_own_ip() -> None:
    """A ``local`` host resolves via get_own_ip (the add-on/same-host path)."""
    comm = _make_comm("local")
    comm._client = None
    comm._hass.async_add_executor_job = AsyncMock(return_value="10.0.0.9")
    client = AsyncMock(spec=HabitronClient)
    with (
        patch(
            "homeassistant.components.habitron.communicate.network.async_get_source_ip",
            new=AsyncMock(return_value="10.0.0.1"),
        ),
        patch(
            "homeassistant.components.habitron.communicate.HabitronClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.habitron.communicate.async_get_integration",
            new=AsyncMock(return_value=MagicMock(version="3.0.2")),
        ),
    ):
        await comm.async_setup()
    assert comm._host == "10.0.0.9"
    assert comm.hbtn_version == "3.0.2"
    client.connect.assert_awaited()


async def test_get_smhub_info_timeout_reraises() -> None:
    """A timeout during the info fetch is re-raised as HabitronTimeoutError."""
    comm = _make_comm()
    comm._client.get_smhub_info = AsyncMock(side_effect=HabitronTimeoutError("t"))
    with pytest.raises(HabitronTimeoutError):
        await comm.get_smhub_info()


async def test_get_smhub_info_generic_error_reraises() -> None:
    """An unexpected error during the info fetch propagates unchanged."""
    comm = _make_comm()
    comm._client.get_smhub_info = AsyncMock(side_effect=ValueError("boom"))
    with pytest.raises(ValueError, match="boom"):
        await comm.get_smhub_info()


def test_hostname_property_returns_cached_value() -> None:
    """The hostname property exposes the cached hub hostname."""
    comm = _make_comm()
    comm._hostname = "smarthub-1"
    assert comm.hostname == "smarthub-1"


async def test_send_devregid_forwards_to_client() -> None:
    """``send_devregid`` (used during device registration) forwards verbatim."""
    comm = _make_comm()
    await comm.send_devregid(5, "abc")
    comm._client.send_devregid.assert_awaited_once_with(5, "abc")
