"""Tests for HIVIDiscoveryScheduler and discovery helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.hivi_speaker import discovery_scheduler as ds_module
from homeassistant.components.hivi_speaker.const import DOMAIN
from homeassistant.components.hivi_speaker.discovery_scheduler import (
    HIVIDiscoveryScheduler,
    _is_safe_location_url,
    parse_local_url,
    parse_ssdp_response,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://192.168.1.1/desc.xml", True),
        ("https://10.0.0.5/x", True),
        ("http://169.254.12.3/foo", True),
        ("ftp://192.168.1.1/x", False),
        ("http://8.8.8.8/x", False),
        ("http://example.com/x", False),
        ("not-a-url", False),
    ],
)
def test_is_safe_location_url(url: str, expected: bool) -> None:
    """Is safe location url."""
    assert _is_safe_location_url(url) is expected


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8/desc.xml",
        "ftp://192.168.1.1/desc.xml",
    ],
)
async def test_parse_local_url_rejects_unsafe_or_non_http(url: str) -> None:
    """Parse local url rejects unsafe or non http."""
    session = MagicMock()
    assert await parse_local_url(session, url) is None
    session.get.assert_not_called()


async def test_parse_local_url_parses_device_xml() -> None:
    """Parse local url parses device xml."""
    device_el = MagicMock()

    def _findtext(tag: str, default: str = "", ns=None) -> str:
        """Return canned XML field values for the fake device element."""
        return {
            "device:manufacturer": "SWAN",
            "device:friendlyName": "Test",
            "device:modelName": "M1",
            "device:UDN": "uuid:test-udn",
        }.get(tag, default)

    device_el.findtext = _findtext
    root = MagicMock()
    root.find = MagicMock(return_value=device_el)

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.text = AsyncMock(return_value="<xml/>")
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.get = MagicMock(return_value=cm)

    with patch(
        "homeassistant.components.hivi_speaker.discovery_scheduler.ET.fromstring",
        return_value=root,
    ):
        out = await parse_local_url(session, "http://192.168.55.10/desc.xml")
    assert out is not None
    assert out["UDN"] == "uuid:test-udn"
    assert out["friendly_name"] == "Test"


def _scheduler(hass: HomeAssistant, entry: MockConfigEntry) -> HIVIDiscoveryScheduler:
    """HIVIDiscoveryScheduler with mocked device_manager (tests)."""
    dm = MagicMock()
    dm.device_data_registry.get_connection_status_counts = MagicMock(
        return_value=(2, 0)
    )
    return HIVIDiscoveryScheduler(
        hass=hass,
        config_entry=entry,
        device_manager=dm,
        base_interval=300,
    )


async def test_discovery_scheduler_async_start_idempotent(
    hass: HomeAssistant,
) -> None:
    """Discovery scheduler async start idempotent."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    with patch.object(sched, "_reschedule", new_callable=AsyncMock) as mock_rs:
        await sched.async_start()
        await sched.async_start()
    assert mock_rs.await_count >= 1
    assert sched._discovery_running is True


async def test_discovery_scheduler_async_stop_clears_timer(
    hass: HomeAssistant,
) -> None:
    """Discovery scheduler async stop clears timer."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    unsub = MagicMock()
    sched._discovery_running = True
    sched._discovery_unsub = unsub
    await sched.async_stop()
    unsub.assert_called_once()
    assert sched._discovery_unsub is None
    assert sched._discovery_running is False


async def test_postpone_discovery_returns_false_when_already_later(
    hass: HomeAssistant,
) -> None:
    """Postpone discovery returns false when already later."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(hours=1)
    with patch.object(sched, "_reschedule", new_callable=AsyncMock) as mock_rs:
        out = await sched.postpone_discovery(delay_seconds=60)
    assert out is False
    mock_rs.assert_not_awaited()


async def test_postpone_discovery_returns_true_and_reschedules(
    hass: HomeAssistant,
) -> None:
    """Postpone discovery returns true and reschedules."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(seconds=10)
    with patch.object(sched, "_reschedule", new_callable=AsyncMock) as mock_rs:
        out = await sched.postpone_discovery(delay_seconds=600)
    assert out is True
    mock_rs.assert_awaited_once()


async def test_schedule_immediate_discovery_force_creates_task(
    hass: HomeAssistant,
) -> None:
    """Schedule immediate discovery force creates task."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    with patch.object(hass, "async_create_task") as mock_ct:
        await sched.schedule_immediate_discovery(force=True)
    mock_ct.assert_called_once()


async def test_schedule_immediate_discovery_updates_next_and_reschedules(
    hass: HomeAssistant,
) -> None:
    """Schedule immediate discovery updates next and reschedules."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(hours=1)
    with patch.object(sched, "_reschedule", new_callable=AsyncMock) as mock_rs:
        await sched.schedule_immediate_discovery(force=False)
    mock_rs.assert_awaited_once()
    assert sched._next_discovery is not None


async def test_reschedule_no_op_when_not_running(hass: HomeAssistant) -> None:
    """Reschedule no op when not running."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = False
    sched._next_discovery = datetime.now()
    with patch.object(hass, "async_create_task") as mock_ct:
        await sched._reschedule()
    mock_ct.assert_not_called()


async def test_reschedule_immediate_when_delay_non_positive(
    hass: HomeAssistant,
) -> None:
    """Reschedule immediate when delay non positive."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() - timedelta(seconds=5)
    with patch.object(hass, "async_create_task") as mock_ct:
        await sched._reschedule()
    mock_ct.assert_called_once()


async def test_run_discovery_perform_adjust_reschedule(
    hass: HomeAssistant,
) -> None:
    """Run discovery perform adjust reschedule."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    with (
        patch.object(sched, "_perform_discovery", new_callable=AsyncMock) as mock_perf,
        patch.object(sched, "_adjust_interval", new_callable=AsyncMock) as mock_adj,
        patch.object(sched, "_reschedule", new_callable=AsyncMock) as mock_rs,
    ):
        await sched._run_discovery()
    mock_perf.assert_awaited_once()
    mock_adj.assert_awaited_once()
    mock_rs.assert_awaited_once()


async def test_discover_all_devices_flattens_and_filters(
    hass: HomeAssistant,
) -> None:
    """Discover all devices flattens and filters."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    raw = [
        {"UDN": "u1", "ip_addr": "192.168.1.1"},
        "skip",
        {"no": "udn"},
        [{"UDN": "u2"}],
    ]
    with patch.object(
        sched, "_discover_private_devices", new_callable=AsyncMock, return_value=raw
    ):
        out = await sched._discover_all_devices()
    assert len(out) == 2
    assert {d["UDN"] for d in out} == {"u1", "u2"}


async def test_adjust_interval_offline_ratio_branches(hass: HomeAssistant) -> None:
    """Adjust interval offline ratio branches."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched.current_interval = 300
    sched.min_interval = 120
    sched.max_interval = 600

    reg = sched.device_manager.device_data_registry
    sched.current_interval = 300
    reg.get_connection_status_counts = MagicMock(return_value=(1, 9))
    await sched._adjust_interval()
    assert sched.current_interval == min(300 * 1.3, 600)

    sched.current_interval = 300
    # offline_ratio must be *strictly* > 0.5 (5/10 == 0.5 hits the fine-tune branch).
    reg.get_connection_status_counts = MagicMock(return_value=(4, 6))
    await sched._adjust_interval()
    assert sched.current_interval == min(300 * 1.1, 600)

    sched.current_interval = 400
    reg.get_connection_status_counts = MagicMock(return_value=(10, 0))
    await sched._adjust_interval()
    assert sched.current_interval == max(400 * 0.9, sched.min_interval)

    sched.current_interval = 200
    reg.get_connection_status_counts = MagicMock(return_value=(7, 2))
    await sched._adjust_interval()
    assert sched.current_interval == max(200 * 0.95, sched.min_interval)


async def test_perform_discovery_sends_signal_when_devices(
    hass: HomeAssistant,
) -> None:
    """Perform discovery sends signal when devices."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    devs = [{"UDN": "x"}]
    with (
        patch.object(
            sched, "_discover_all_devices", new_callable=AsyncMock, return_value=devs
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.async_dispatcher_send"
        ) as mock_send,
    ):
        await sched._perform_discovery()
    mock_send.assert_called_once()


async def test_perform_discovery_swallows_client_errors(hass: HomeAssistant) -> None:
    """Perform discovery swallows client errors."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    with patch.object(
        sched,
        "_discover_all_devices",
        new_callable=AsyncMock,
        side_effect=OSError("boom"),
    ):
        await sched._perform_discovery()


async def test_adjust_interval_swallows_registry_errors(hass: HomeAssistant) -> None:
    """Adjust interval swallows registry errors."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched.device_manager.device_data_registry.get_connection_status_counts = MagicMock(
        side_effect=RuntimeError("counts failed")
    )
    before = sched.current_interval
    await sched._adjust_interval()
    assert sched.current_interval == before


async def test_reschedule_returns_when_no_next_discovery(hass: HomeAssistant) -> None:
    """Reschedule returns when no next discovery."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = None
    with patch.object(hass, "async_create_task") as mock_ct:
        await sched._reschedule()
    mock_ct.assert_not_called()


async def test_reschedule_cancels_prior_timer(hass: HomeAssistant) -> None:
    """Reschedule cancels prior timer."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(seconds=30)
    old_unsub = MagicMock()
    sched._discovery_unsub = old_unsub
    with patch(
        "homeassistant.components.hivi_speaker.discovery_scheduler.async_call_later",
        return_value=MagicMock(),
    ):
        await sched._reschedule()
    old_unsub.assert_called_once()


async def test_reschedule_unsub_cancel_raises(hass: HomeAssistant) -> None:
    """Reschedule unsub cancel raises."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(seconds=10)
    sched._discovery_unsub = MagicMock(side_effect=RuntimeError("cancel boom"))
    with patch(
        "homeassistant.components.hivi_speaker.discovery_scheduler.async_call_later",
        return_value=MagicMock(),
    ) as mock_later:
        await sched._reschedule()
    mock_later.assert_called_once()


async def test_reschedule_immediate_path_create_task_raises(
    hass: HomeAssistant,
) -> None:
    """Reschedule immediate path create task raises."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() - timedelta(seconds=1)
    with patch.object(hass, "async_create_task", side_effect=OSError("no task")):
        await sched._reschedule()


async def test_reschedule_clamps_delay_below_point_one(hass: HomeAssistant) -> None:
    """Reschedule clamps delay below point one."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(milliseconds=20)
    with patch(
        "homeassistant.components.hivi_speaker.discovery_scheduler.async_call_later"
    ) as mock_later:
        await sched._reschedule()
    assert mock_later.call_args[0][1] == 0.1


async def test_reschedule_registers_delayed_callback(hass: HomeAssistant) -> None:
    """Reschedule registers delayed callback."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(seconds=5)
    timer_handle = MagicMock()
    with patch(
        "homeassistant.components.hivi_speaker.discovery_scheduler.async_call_later",
        return_value=timer_handle,
    ):
        await sched._reschedule()
    assert sched._discovery_unsub is timer_handle


async def test_reschedule_call_later_fails_then_backoff(hass: HomeAssistant) -> None:
    """Reschedule call later fails then backoff."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(seconds=5)
    fallback = MagicMock()
    with patch(
        "homeassistant.components.hivi_speaker.discovery_scheduler.async_call_later",
        side_effect=[OSError("primary fail"), fallback],
    ):
        await sched._reschedule()
    assert sched._discovery_unsub is fallback


async def test_reschedule_backoff_callback_also_fails(hass: HomeAssistant) -> None:
    """Reschedule backoff callback also fails."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(seconds=5)
    with patch(
        "homeassistant.components.hivi_speaker.discovery_scheduler.async_call_later",
        side_effect=[OSError("a"), OSError("b")],
    ):
        await sched._reschedule()
    assert sched._discovery_unsub is None


async def test_run_discovery_sets_backoff_on_perform_error(
    hass: HomeAssistant,
) -> None:
    """Run discovery sets backoff on perform error."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    with (
        patch.object(
            sched, "_perform_discovery", side_effect=ValueError("discovery bad")
        ),
        patch.object(sched, "_reschedule", new_callable=AsyncMock),
    ):
        await sched._run_discovery()


async def test_discover_private_devices_executor_raises(hass: HomeAssistant) -> None:
    """Discover private devices executor raises."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    with patch.object(
        hass, "async_add_executor_job", side_effect=TimeoutError("scan failed")
    ):
        out = await sched._discover_private_devices()
    assert out == []


async def test_discover_private_devices_no_raw_responses(hass: HomeAssistant) -> None:
    """Discover private devices no raw responses."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    with patch.object(
        hass, "async_add_executor_job", new_callable=AsyncMock, return_value=[]
    ):
        out = await sched._discover_private_devices()
    assert out == []


async def test_discover_private_devices_parses_with_mocked_session(
    hass: HomeAssistant,
) -> None:
    """Discover private devices parses with mocked session."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    raw = [
        (
            "HTTP/1.1 200 OK\r\nlocation: http://192.168.88.1/d.xml\r\n",
            ("192.168.88.2", 1900),
        )
    ]
    session = MagicMock()
    with (
        patch.object(
            hass, "async_add_executor_job", new_callable=AsyncMock, return_value=raw
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.parse_local_url",
            new_callable=AsyncMock,
            return_value={
                "UDN": "uuid:one",
                "friendly_name": "A",
                "manufacturer": "M",
                "model_name": "X",
            },
        ),
    ):
        out = await sched._discover_private_devices()
    assert len(out) == 1
    assert out[0]["UDN"] == "uuid:one"
    assert out[0]["ip_addr"] == "192.168.88.2"


async def test_discover_private_parse_one_swallows_errors(hass: HomeAssistant) -> None:
    """Discover private parse one swallows errors."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    raw = [("bad", ("10.0.0.1", 1900))]
    with (
        patch.object(
            hass, "async_add_executor_job", new_callable=AsyncMock, return_value=raw
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.parse_local_url",
            new_callable=AsyncMock,
            side_effect=RuntimeError("parse boom"),
        ),
    ):
        out = await sched._discover_private_devices()
    assert out == []


def test_scan_speaker_sync_mocked_socket() -> None:
    """Scan speaker sync mocked socket."""
    mock_sock = MagicMock()
    mock_sock.recvfrom = MagicMock(side_effect=[TimeoutError(), OSError()])
    mock_sock.sendto = MagicMock()
    with patch.object(ds_module.socket, "socket", return_value=mock_sock):
        out = ds_module._scan_speaker_sync()
    assert isinstance(out, list)
    mock_sock.close.assert_called_once()


async def test_parse_local_url_client_error_returns_none() -> None:
    """Parse local url client error returns none."""
    session = MagicMock()
    session.get = MagicMock(side_effect=aiohttp.ClientConnectionError("down"))
    assert await parse_local_url(session, "http://192.168.30.1/d.xml") is None


async def test_reschedule_timer_callback_schedules_discovery(
    hass: HomeAssistant,
) -> None:
    """Reschedule timer callback schedules discovery."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    sched._discovery_running = True
    sched._next_discovery = datetime.now() + timedelta(seconds=2)
    captured: list = []

    def _fake_later(h, delay, cb):
        cb(None)
        return MagicMock()

    mock_loop = MagicMock()

    def _capture(fn, *a, **kw):
        captured.append(fn)

    mock_loop.call_soon_threadsafe = MagicMock(side_effect=_capture)
    with (
        patch.object(hass, "loop", mock_loop, create=True),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.async_call_later",
            side_effect=_fake_later,
        ),
        patch.object(hass, "async_create_task") as mock_ct,
    ):
        await sched._reschedule()
        assert captured
        captured[0]()
        mock_ct.assert_called_once()


async def test_discover_private_skips_when_parse_local_returns_none(
    hass: HomeAssistant,
) -> None:
    """Discover private skips when parse local returns none."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    raw = [
        ("HTTP/1.1 200\r\nlocation: http://192.168.1.1/d.xml\r\n", ("10.0.0.1", 1900))
    ]
    with (
        patch.object(
            hass, "async_add_executor_job", new_callable=AsyncMock, return_value=raw
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.parse_local_url",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        out = await sched._discover_private_devices()
    assert out == []


async def test_discover_private_skips_when_udn_missing(hass: HomeAssistant) -> None:
    """Discover private skips when udn missing."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    raw = [
        ("HTTP/1.1 200\r\nlocation: http://192.168.1.1/d.xml\r\n", ("10.0.0.1", 1900))
    ]
    with (
        patch.object(
            hass, "async_add_executor_job", new_callable=AsyncMock, return_value=raw
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.parse_local_url",
            new_callable=AsyncMock,
            return_value={"friendly_name": "x"},
        ),
    ):
        out = await sched._discover_private_devices()
    assert out == []


async def test_discover_private_deduplicates_same_udn(hass: HomeAssistant) -> None:
    """Discover private deduplicates same udn."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    sched = _scheduler(hass, entry)
    raw = [
        ("a", ("10.0.0.1", 1900)),
        ("b", ("10.0.0.2", 1900)),
    ]
    dev = {"UDN": "uuid:same", "friendly_name": "F"}
    with (
        patch.object(
            hass, "async_add_executor_job", new_callable=AsyncMock, return_value=raw
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.hivi_speaker.discovery_scheduler.parse_local_url",
            new_callable=AsyncMock,
            return_value=dev,
        ),
    ):
        out = await sched._discover_private_devices()
    assert len(out) == 1


async def test_parse_local_url_xml_without_device_node() -> None:
    """Parse local url xml without device node."""
    root = MagicMock()
    root.find = MagicMock(return_value=None)
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.text = AsyncMock(return_value="<root/>")
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.get = MagicMock(return_value=cm)
    with patch(
        "homeassistant.components.hivi_speaker.discovery_scheduler.ET.fromstring",
        return_value=root,
    ):
        assert await parse_local_url(session, "http://192.168.40.1/d.xml") is None


def test_parse_ssdp_response_skips_line_when_split_raises_valueerror() -> None:
    """Parse ssdp response skips line when split raises valueerror."""

    class _BadSsdpLine:
        """Stub line; split on ':' raises so parse_ssdp skips that header."""

        __slots__ = ("_text",)

        def __init__(self, text: str) -> None:
            self._text = text

        def __contains__(self, item: object) -> bool:
            return item in self._text

        def split(self, sep: str, maxsplit: int = -1) -> list[str]:
            if sep == ":":
                raise ValueError("forced")
            return self._text.split(sep, maxsplit)

    # Fake response_text.split("\r\n") so the body line stays a _BadSsdpLine.
    class _FakeResponse:
        """Minimal response_text with custom CRLF split."""

        def split(self, sep, maxsplit=-1):
            if sep == "\r\n":
                return ["HTTP/1.1 206 Partial", _BadSsdpLine("server: dropped")]
            return []

    out = parse_ssdp_response(_FakeResponse(), ("10.0.0.5", 1900))
    assert out["ip"] == "10.0.0.5"
    assert out["connection_status"].startswith("HTTP/1.1")
    assert "server" not in out


def test_scan_speaker_sync_sendto_oserror_exits_loop() -> None:
    """Scan speaker sync sendto oserror exits loop."""
    mock_sock = MagicMock()
    mock_sock.sendto = MagicMock(side_effect=OSError("send fail"))
    mock_sock.recvfrom = MagicMock(side_effect=TimeoutError())
    with patch.object(ds_module.socket, "socket", return_value=mock_sock):
        out = ds_module._scan_speaker_sync()
    assert out == []


def test_scan_speaker_sync_recvfrom_data_then_oserror() -> None:
    """Scan speaker sync recvfrom data then oserror."""
    mock_sock = MagicMock()
    mock_sock.sendto = MagicMock()
    mock_sock.recvfrom = MagicMock(
        side_effect=[
            (b"HTTP/1.1 200\r\n\r\n", ("192.168.1.1", 1900)),
            OSError(),
        ]
    )
    with patch.object(ds_module.socket, "socket", return_value=mock_sock):
        out = ds_module._scan_speaker_sync()
    assert len(out) == 1
