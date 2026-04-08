"""Tests for HIVIDeviceManager (heavy dependencies mocked)."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hivi_speaker.const import (
    DEVICE_OFFLINE_THRESHOLD,
    DOMAIN,
    SIGNAL_DEVICE_STATUS_UPDATED,
)
from homeassistant.components.hivi_speaker.device import (
    ConnectionStatus,
    HIVIDevice,
    SlaveDeviceInfo,
    SyncGroupStatus,
)
from homeassistant.components.hivi_speaker.device_manager import HIVIDeviceManager
from homeassistant.core import HomeAssistant, StateMachine

from tests.common import MockConfigEntry


def _swallow_discovery_worker_task(coro):
    if inspect.iscoroutine(coro):
        coro.close()
    worker = AsyncMock()
    worker.done = MagicMock(return_value=True)
    worker.cancel = MagicMock()
    return worker


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def device_manager(hass: HomeAssistant, config_entry: MockConfigEntry) -> HIVIDeviceManager:
    with patch.object(hass, "async_create_task", side_effect=_swallow_discovery_worker_task):
        return HIVIDeviceManager(hass, config_entry)


def test_master_slave_list_contains_uuid() -> None:
    info = SlaveDeviceInfo(
        friendly_name="S",
        ssid="",
        mask=None,
        volume=0,
        mute=False,
        channel=0,
        battery=None,
        ip_addr="1.1.1.1",
        version="1",
        uuid="u1",
    )
    dev = HIVIDevice(speaker_device_id="m", slave_device_list=[info])
    assert HIVIDeviceManager._master_slave_list_contains_uuid(dev, "u1") is True
    assert HIVIDeviceManager._master_slave_list_contains_uuid(dev, "nope") is False


def test_suggest_area_from_name(device_manager: HIVIDeviceManager) -> None:
    assert device_manager._suggest_area_from_name("Living room speaker") == "living room"
    assert device_manager._suggest_area_from_name("Kitchen SWAN") == "kitchen"
    assert device_manager._suggest_area_from_name("random") is None


def test_create_device_obj_from_discovered_device_info(
    device_manager: HIVIDeviceManager,
) -> None:
    obj = device_manager._create_device_obj_from_discovered_device_info(
        {
            "UDN": "uuid:1",
            "friendly_name": "FN",
            "model_name": "Mod",
            "manufacturer": "Mfr",
            "ip_addr": "192.168.1.5",
        }
    )
    assert obj.speaker_device_id == "uuid:1"
    assert obj.friendly_name == "FN"
    assert obj.ip_addr == "192.168.1.5"


def test_set_add_entities_callback(device_manager: HIVIDeviceManager) -> None:
    cb = MagicMock()
    device_manager.set_add_entities_callback("switch", cb)
    assert device_manager._add_entities_callbacks["switch"] is cb


async def test_async_setup_wires_registry_and_starts_children(
    hass: HomeAssistant,
    device_manager: HIVIDeviceManager,
) -> None:
    device_manager.device_data_registry.async_load = AsyncMock()
    device_manager.discovery_scheduler.async_start = AsyncMock()
    device_manager.group_coordinator.async_start = AsyncMock()
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.async_dispatcher_connect",
        return_value=MagicMock(),
    ) as mock_dc:
        await device_manager.async_setup()
    mock_dc.assert_called_once()
    device_manager.device_data_registry.async_load.assert_awaited_once()
    device_manager.discovery_scheduler.async_start.assert_awaited_once()
    device_manager.group_coordinator.async_start.assert_awaited_once()
    assert device_manager._unsub_discovery is not None


async def test_async_cleanup_stops_children_and_worker(
    device_manager: HIVIDeviceManager,
) -> None:
    device_manager.discovery_scheduler.async_stop = AsyncMock()
    device_manager.group_coordinator.async_stop = AsyncMock()
    device_manager.device_data_registry.async_shutdown = AsyncMock()
    device_manager._unsub_discovery = MagicMock()
    unsub = device_manager._unsub_discovery
    done_future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    done_future.set_result(None)
    device_manager._handle_discovery_worker = done_future
    await device_manager.async_cleanup()
    unsub.assert_called_once()
    device_manager.discovery_scheduler.async_stop.assert_awaited_once()
    device_manager.group_coordinator.async_stop.assert_awaited_once()
    device_manager.device_data_registry.async_shutdown.assert_awaited_once()
    assert done_future.cancelled() or done_future.done()
    assert device_manager._handle_discovery_worker is None


async def test_async_manual_discovery_delegates(device_manager: HIVIDeviceManager) -> None:
    device_manager.discovery_scheduler.schedule_immediate_discovery = AsyncMock()
    await device_manager.async_manual_discovery()
    device_manager.discovery_scheduler.schedule_immediate_discovery.assert_awaited_once_with(
        force=False
    )


async def test_refresh_and_postpone_discovery_delegate(
    device_manager: HIVIDeviceManager,
) -> None:
    device_manager.discovery_scheduler.schedule_immediate_discovery = AsyncMock()
    device_manager.discovery_scheduler.postpone_discovery = AsyncMock()
    await device_manager.refresh_discovery()
    await device_manager.postpone_discovery()
    device_manager.discovery_scheduler.schedule_immediate_discovery.assert_awaited()
    device_manager.discovery_scheduler.postpone_discovery.assert_awaited()


async def test_async_register_device(device_manager: HIVIDeviceManager) -> None:
    dev = HIVIDevice(speaker_device_id="spk1", friendly_name="Living HiVi")
    mock_reg = MagicMock()
    mock_reg.async_get_or_create = MagicMock(
        return_value=SimpleNamespace(id="ha-device-99")
    )
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.dr.async_get",
        return_value=mock_reg,
    ):
        ha_id = await device_manager.async_register_device(dev)
    assert ha_id == "ha-device-99"
    mock_reg.async_get_or_create.assert_called_once()


async def test_discovery_enqueue(device_manager: HIVIDeviceManager) -> None:
    await device_manager._discovery_enqueue([{"UDN": "x"}])
    assert device_manager._discovery_queue.qsize() == 1


async def test_handle_discovered_devices_runs_pipeline(
    device_manager: HIVIDeviceManager,
) -> None:
    with (
        patch.object(
            device_manager, "_save_discovered_devices", new_callable=AsyncMock
        ) as mock_save,
        patch.object(
            device_manager, "_update_all_device_statuses", new_callable=AsyncMock
        ) as mock_upd,
        patch.object(
            device_manager, "_add_or_remove_switches", new_callable=AsyncMock
        ) as mock_sw,
        patch.object(
            device_manager,
            "_update_device_entity_states",
            new_callable=AsyncMock,
        ) as mock_ent,
        patch.object(
            device_manager, "_device_offline_process", new_callable=AsyncMock
        ) as mock_off,
    ):
        await device_manager._handle_discovered_devices([{"UDN": "u1"}])
    mock_save.assert_awaited_once()
    mock_upd.assert_awaited_once()
    mock_sw.assert_awaited_once()
    mock_ent.assert_awaited_once()
    mock_off.assert_awaited_once()


async def test_save_discovered_skips_missing_udn(
    device_manager: HIVIDeviceManager,
) -> None:
    device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    device_manager.async_register_device = AsyncMock()
    await device_manager._save_discovered_devices([{"ip_addr": "1.1.1.1"}])
    device_manager.async_register_device.assert_not_awaited()


async def test_save_discovered_updates_existing(
    device_manager: HIVIDeviceManager,
) -> None:
    existing = HIVIDevice(
        speaker_device_id="uuid:old",
        ha_device_id="ha-1",
        friendly_name="Old",
        ip_addr="10.0.0.1",
    ).model_dump(mode="json")
    device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=existing)
    )
    device_manager.device_data_registry.set_device_dict_by_ha_device_id = MagicMock()
    await device_manager._save_discovered_devices(
        [
            {
                "UDN": "uuid:old",
                "ip_addr": "10.0.0.2",
                "friendly_name": "New",
            }
        ]
    )
    device_manager.device_data_registry.set_device_dict_by_ha_device_id.assert_called()


async def test_save_discovered_registers_new_when_missing_in_registry(
    device_manager: HIVIDeviceManager,
) -> None:
    device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    device_manager.async_register_device = AsyncMock(return_value="ha-new")
    device_manager.device_data_registry.set_device_dict_by_ha_device_id = MagicMock()
    await device_manager._save_discovered_devices(
        [
            {
                "UDN": "uuid:new",
                "friendly_name": "N",
                "ip_addr": "192.168.1.2",
            }
        ]
    )
    device_manager.async_register_device.assert_awaited_once()
    device_manager.device_data_registry.set_device_dict_by_ha_device_id.assert_called()


async def test_async_remove_entities_for_device_none(
    device_manager: HIVIDeviceManager,
) -> None:
    ent_reg = MagicMock()
    ent_reg.entities.get_entries_for_device_id = MagicMock(return_value=[])
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.er.async_get",
        return_value=ent_reg,
    ):
        await device_manager.async_remove_entities_for_device("d1")
    ent_reg.async_remove.assert_not_called()


async def test_async_remove_entities_for_device_removes_each(
    device_manager: HIVIDeviceManager,
) -> None:
    e1 = SimpleNamespace(entity_id="switch.a")
    ent_reg = MagicMock()
    ent_reg.entities.get_entries_for_device_id = MagicMock(return_value=[e1])
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.er.async_get",
        return_value=ent_reg,
    ):
        await device_manager.async_remove_entities_for_device("d1")
    ent_reg.async_remove.assert_called_once_with("switch.a")


async def test_async_remove_device_with_entities(
    device_manager: HIVIDeviceManager,
) -> None:
    with (
        patch.object(
            device_manager,
            "async_remove_entities_for_device",
            new_callable=AsyncMock,
        ) as mock_ent,
        patch(
            "homeassistant.components.hivi_speaker.device_manager.dr.async_get",
            return_value=MagicMock(),
        ) as mock_dr,
    ):
        await device_manager.async_remove_device_with_entities("d9")
    mock_ent.assert_awaited_once_with("d9")
    mock_dr.return_value.async_remove_device.assert_called_once_with("d9")


async def test_async_remove_device_with_entities_swallows_registry_error(
    device_manager: HIVIDeviceManager,
) -> None:
    mock_dr = MagicMock()
    mock_dr.async_remove_device = MagicMock(side_effect=RuntimeError("reg fail"))
    with (
        patch.object(
            device_manager,
            "async_remove_entities_for_device",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.hivi_speaker.device_manager.dr.async_get",
            return_value=mock_dr,
        ),
    ):
        await device_manager.async_remove_device_with_entities("d-bad")


async def test_fetch_device_status_logs_non_dict_status(
    device_manager: HIVIDeviceManager,
) -> None:
    inner = MagicMock()
    inner.get_device_status = AsyncMock(return_value="not-a-dict")
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=inner)
    ctx.__aexit__ = AsyncMock(return_value=None)
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.HivicoClient",
        return_value=ctx,
    ):
        out = await device_manager._fetch_device_status(
            HIVIDevice(speaker_device_id="s", ip_addr="192.168.1.1")
        )
    assert out == "not-a-dict"


async def test_fetch_slave_device_returns_payload(
    device_manager: HIVIDeviceManager,
) -> None:
    payload = {"slaves": 0, "slave_list": []}
    inner = MagicMock()
    inner.get_slave_devices = AsyncMock(return_value=payload)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=inner)
    ctx.__aexit__ = AsyncMock(return_value=None)
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.HivicoClient",
        return_value=ctx,
    ):
        out = await device_manager._fetch_slave_device(
            HIVIDevice(speaker_device_id="s", ip_addr="192.168.1.2")
        )
    assert out is payload


async def test_remove_control_entities_by_speaker_device_id(
    device_manager: HIVIDeviceManager,
) -> None:
    ent = SimpleNamespace(entity_id="switch.m_slave_s1", unique_id="m_slave_s1")
    ent_reg = MagicMock()
    ent_reg.entities = MagicMock()
    ent_reg.entities.values = MagicMock(return_value=[ent])
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.er.async_get",
        return_value=ent_reg,
    ):
        await device_manager.remove_control_entities_by_speaker_device_id("s1")
    ent_reg.async_remove.assert_called_once_with("switch.m_slave_s1")


async def test_remove_control_entities_no_match_returns_early(
    device_manager: HIVIDeviceManager,
) -> None:
    ent = SimpleNamespace(entity_id="switch.a", unique_id="m_slave_other")
    ent_reg = MagicMock()
    ent_reg.entities = MagicMock()
    ent_reg.entities.values = MagicMock(return_value=[ent])
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.er.async_get",
        return_value=ent_reg,
    ):
        await device_manager.remove_control_entities_by_speaker_device_id("ghost")
    ent_reg.async_remove.assert_not_called()


async def test_remove_control_entities_swallows_registry_error(
    device_manager: HIVIDeviceManager,
) -> None:
    ent_reg = MagicMock()
    ent_reg.entities = MagicMock()
    ent_reg.entities.values = MagicMock(side_effect=RuntimeError("iter fail"))
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.er.async_get",
        return_value=ent_reg,
    ):
        await device_manager.remove_control_entities_by_speaker_device_id("s1")


async def test_fetch_device_status_redacts_psk_in_logs(
    device_manager: HIVIDeviceManager,
) -> None:
    inner = MagicMock()
    inner.get_device_status = AsyncMock(
        return_value={"ssid": "x", "psk": "secret"}
    )
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=inner)
    ctx.__aexit__ = AsyncMock(return_value=None)
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.HivicoClient",
        return_value=ctx,
    ):
        out = await device_manager._fetch_device_status(
            HIVIDevice(speaker_device_id="s", ip_addr="192.168.1.1")
        )
    assert out is not None
    assert out.get("psk") == "secret"


async def test_get_devices_for_device_filters_domain(
    hass: HomeAssistant,
    device_manager: HIVIDeviceManager,
) -> None:
    d_ok = SimpleNamespace(identifiers={(DOMAIN, "u1")})
    d_other = SimpleNamespace(identifiers={("mqtt", "x")})
    mock_dr = MagicMock()
    mock_dr.devices = {"a": d_ok, "b": d_other}
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.dr.async_get",
        return_value=mock_dr,
    ):
        devices = await device_manager._get_devices_for_device()
    assert devices == [d_ok]


async def test_get_entities_for_device(device_manager: HIVIDeviceManager) -> None:
    e1 = SimpleNamespace(device_id="d1", entity_id="x.y")
    e2 = SimpleNamespace(device_id="d2", entity_id="x.z")
    ent_reg = MagicMock()
    ent_reg.entities = MagicMock()
    ent_reg.entities.values = MagicMock(return_value=[e1, e2])
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.er.async_get",
        return_value=ent_reg,
    ):
        out = await device_manager._get_entities_for_device("d1")
    assert out == [e1]


async def test_discovery_worker_swallows_handler_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """_handle_discovery_loop logs and continues when _handle_discovered_devices fails."""
    mgr = HIVIDeviceManager(hass, config_entry)
    try:
        mgr._handle_discovered_devices = AsyncMock(side_effect=RuntimeError("handler boom"))
        await mgr._discovery_queue.put([{"UDN": "any"}])
        await asyncio.wait_for(mgr._discovery_queue.join(), timeout=5.0)
    finally:
        mgr._handle_discovery_worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await mgr._handle_discovery_worker


async def test_update_all_device_statuses_skips_missing_dict(
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "u1")}, name="N")
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=None,
        ),
    ):
        await device_manager._update_all_device_statuses()


async def test_update_all_device_statuses_fetch_raises(
    device_manager: HIVIDeviceManager,
) -> None:
    dct = HIVIDevice(
        speaker_device_id="spk1",
        friendly_name="One",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "spk1")}, name="One")
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=dct,
        ),
        patch.object(
            device_manager,
            "_fetch_device_status",
            new_callable=AsyncMock,
            side_effect=RuntimeError("net down"),
        ),
    ):
        await device_manager._update_all_device_statuses()


async def test_update_all_device_statuses_slave_group_branch(
    device_manager: HIVIDeviceManager,
) -> None:
    dct = HIVIDevice(
        speaker_device_id="spk1",
        friendly_name="One",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "spk1")}, name="One")
    status = {"group": 1, "WifiChannel": "1", "ssid": "s", "uuid": "z"}
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=dct,
        ),
        patch.object(
            device_manager.device_data_registry,
            "set_device_dict_by_ha_device_id",
            MagicMock(),
        ) as mock_set,
        patch.object(
            device_manager,
            "_fetch_device_status",
            new_callable=AsyncMock,
            return_value=status,
        ),
    ):
        await device_manager._update_all_device_statuses()
    mock_set.assert_called()


async def test_update_all_device_statuses_removes_slave_devices(
    device_manager: HIVIDeviceManager,
) -> None:
    master = SimpleNamespace(id="dm", identifiers={(DOMAIN, "m")}, name="Master")
    orphan = SimpleNamespace(id="ds", identifiers={(DOMAIN, "orphan-slave")}, name="Orphan")
    master_dict = HIVIDevice(
        speaker_device_id="m",
        friendly_name="M",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
        slave_device_list=[
            SlaveDeviceInfo(
                friendly_name="O",
                ssid="",
                mask=None,
                volume=0,
                mute=False,
                channel=0,
                battery=None,
                ip_addr="10.0.0.2",
                version="1",
                uuid="orphan-slave",
            )
        ],
    ).model_dump(mode="json")
    status = {
        "group": 0,
        "slaves": 1,
        "slave_list": [
            {
                "name": "O",
                "ip": "10.0.0.2",
                "uuid": "orphan-slave",
                "ssid": "",
                "mask": None,
                "volume": 0,
                "mute": False,
                "channel": 0,
                "battery": None,
                "version": "1",
            }
        ],
        "WifiChannel": "6",
        "ssid": "w",
    }
    def _dict_for_device(ha_device_id: str):
        return master_dict if ha_device_id == "dm" else None

    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[master, orphan],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            side_effect=_dict_for_device,
        ),
        patch.object(
            device_manager,
            "_fetch_device_status",
            new_callable=AsyncMock,
            return_value=status,
        ),
        patch.object(
            device_manager,
            "_fetch_slave_device",
            new_callable=AsyncMock,
            return_value=status,
        ),
        patch.object(
            device_manager,
            "async_remove_device_with_entities",
            new_callable=AsyncMock,
        ) as mock_rm,
    ):
        await device_manager._update_all_device_statuses()
    mock_rm.assert_awaited_once_with("ds")


async def test_update_all_fetch_slave_raises_sets_standalone(
    device_manager: HIVIDeviceManager,
) -> None:
    dct = HIVIDevice(
        speaker_device_id="spk1",
        friendly_name="One",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "spk1")}, name="One")
    status = {"group": 0, "WifiChannel": "1", "ssid": "s", "uuid": "z"}
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=dct,
        ),
        patch.object(
            device_manager.device_data_registry,
            "set_device_dict_by_ha_device_id",
            MagicMock(),
        ) as mock_set,
        patch.object(
            device_manager,
            "_fetch_device_status",
            new_callable=AsyncMock,
            return_value=status,
        ),
        patch.object(
            device_manager,
            "_fetch_slave_device",
            new_callable=AsyncMock,
            side_effect=OSError("slave list down"),
        ),
    ):
        await device_manager._update_all_device_statuses()
    mock_set.assert_called()
    saved = mock_set.call_args[0][1]
    assert saved.get("sync_group_status") == SyncGroupStatus.STANDALONE.value


async def test_update_all_slave_num_zero_is_standalone(
    device_manager: HIVIDeviceManager,
) -> None:
    dct = HIVIDevice(
        speaker_device_id="spk1",
        friendly_name="One",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "spk1")}, name="One")
    status = {"group": 0, "WifiChannel": "1", "ssid": "s", "uuid": "z"}
    slave_empty = {"slaves": 0, "slave_list": []}
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=dct,
        ),
        patch.object(
            device_manager.device_data_registry,
            "set_device_dict_by_ha_device_id",
            MagicMock(),
        ) as mock_set,
        patch.object(
            device_manager,
            "_fetch_device_status",
            new_callable=AsyncMock,
            return_value=status,
        ),
        patch.object(
            device_manager,
            "_fetch_slave_device",
            new_callable=AsyncMock,
            return_value=slave_empty,
        ),
    ):
        await device_manager._update_all_device_statuses()
    saved = mock_set.call_args[0][1]
    assert saved.get("sync_group_status") == SyncGroupStatus.STANDALONE.value


async def test_update_all_skips_second_pass_when_no_domain_identifier(
    device_manager: HIVIDeviceManager,
) -> None:
    master = SimpleNamespace(id="dm", identifiers={(DOMAIN, "m")}, name="Master")
    no_domain = SimpleNamespace(id="dx", identifiers={("mqtt", "x")}, name="X")
    master_dict = HIVIDevice(
        speaker_device_id="m",
        friendly_name="M",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    status = {"group": 1, "WifiChannel": "1", "ssid": "s", "uuid": "m"}
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[master, no_domain],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            side_effect=lambda ha_device_id: master_dict if ha_device_id == "dm" else None,
        ),
        patch.object(
            device_manager,
            "_fetch_device_status",
            new_callable=AsyncMock,
            return_value=status,
        ),
        patch.object(
            device_manager,
            "async_remove_device_with_entities",
            new_callable=AsyncMock,
        ) as mock_rm,
    ):
        await device_manager._update_all_device_statuses()
    mock_rm.assert_not_called()


async def test_add_or_remove_switches_removes_invalid_slave_entity(
    hass: HomeAssistant,
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "master1")}, name="M")
    bad_ent = SimpleNamespace(
        entity_id="switch.master1_slave_bad",
        unique_id="master1_slave_baduuid",
    )
    master_dict = HIVIDevice(
        speaker_device_id="master1",
        friendly_name="M",
        hardware="generic",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
        slave_device_list=[],
    ).model_dump(mode="json")
    ent_reg = MagicMock()
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[bad_ent],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=master_dict,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_speaker_device_id",
            return_value=None,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_available_slave_device_dict_list",
            return_value=[],
        ),
        patch(
            "homeassistant.components.hivi_speaker.device_manager.er.async_get",
            return_value=ent_reg,
        ),
    ):
        await device_manager._add_or_remove_switches()
    ent_reg.async_remove.assert_called_once_with("switch.master1_slave_bad")


async def test_add_or_remove_switches_skips_incompatible_hardware(
    hass: HomeAssistant,
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "master1")}, name="M")
    master_dict = HIVIDevice(
        speaker_device_id="master1",
        friendly_name="M",
        hardware="swan-pro",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    slave_cand = {
        "speaker_device_id": "slave1",
        "friendly_name": "S",
        "hardware": "other",
        "sync_group_status": "standalone",
        "connection_status": ConnectionStatus.ONLINE.value,
    }
    add_cb = MagicMock()
    device_manager.set_add_entities_callback("switch", add_cb)
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=master_dict,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_available_slave_device_dict_list",
            return_value=[slave_cand],
        ),
        patch.object(StateMachine, "get", return_value=None),
    ):
        await device_manager._add_or_remove_switches()
    add_cb.assert_not_called()


async def test_add_or_remove_switches_no_platform_callback(
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "master1")}, name="M")
    master_dict = HIVIDevice(
        speaker_device_id="master1",
        friendly_name="M",
        hardware="swan-x",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    slave_cand = {
        "speaker_device_id": "slave1",
        "friendly_name": "S",
        "hardware": "swan-y",
        "sync_group_status": "standalone",
        "connection_status": ConnectionStatus.ONLINE.value,
    }
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=master_dict,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_available_slave_device_dict_list",
            return_value=[slave_cand],
        ),
        patch.object(StateMachine, "get", return_value=None),
    ):
        await device_manager._add_or_remove_switches()


async def test_add_or_remove_switches_skips_when_device_dict_missing(
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="dmiss", identifiers={(DOMAIN, "x")}, name="X")
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=None,
        ),
    ):
        await device_manager._add_or_remove_switches()


async def test_add_or_remove_keeps_orphan_slave_switch_when_on_master_roster(
    hass: HomeAssistant,
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "master1")}, name="M")
    keep_uuid = "on-roster"
    orphan_ent = SimpleNamespace(
        entity_id=f"switch.master1_slave_{keep_uuid}",
        unique_id=f"master1_slave_{keep_uuid}",
    )
    master_dict = HIVIDevice(
        speaker_device_id="master1",
        friendly_name="M",
        hardware="swan-x",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.MASTER,
        slave_device_list=[
            SlaveDeviceInfo(
                friendly_name="K",
                ssid="",
                mask=None,
                volume=0,
                mute=False,
                channel=0,
                battery=None,
                ip_addr="1.1.1.1",
                version="1",
                uuid=keep_uuid,
            )
        ],
    ).model_dump(mode="json")
    ent_reg = MagicMock()
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[orphan_ent],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=master_dict,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_speaker_device_id",
            return_value=None,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_available_slave_device_dict_list",
            return_value=[],
        ),
        patch(
            "homeassistant.components.hivi_speaker.device_manager.er.async_get",
            return_value=ent_reg,
        ),
    ):
        await device_manager._add_or_remove_switches()
    ent_reg.async_remove.assert_not_called()


async def test_add_or_remove_same_non_swan_hardware_creates_switch(
    hass: HomeAssistant,
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "master1")}, name="M")
    master_dict = HIVIDevice(
        speaker_device_id="master1",
        friendly_name="M",
        hardware="generic-a",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    slave_cand = {
        "speaker_device_id": "slave1",
        "friendly_name": "S",
        "hardware": "generic-a",
        "sync_group_status": "standalone",
        "connection_status": ConnectionStatus.ONLINE.value,
    }
    add_cb = MagicMock()
    device_manager.set_add_entities_callback("switch", add_cb)
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=master_dict,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_available_slave_device_dict_list",
            return_value=[slave_cand],
        ),
        patch.object(StateMachine, "get", return_value=None),
    ):
        await device_manager._add_or_remove_switches()
    add_cb.assert_called_once()


async def test_add_or_remove_existing_switch_on_state_skips_duplicate(
    hass: HomeAssistant,
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "master1")}, name="M")
    existing = SimpleNamespace(
        entity_id="switch.master1_slave_slave1",
        unique_id="master1_slave_slave1",
    )
    master_dict = HIVIDevice(
        speaker_device_id="master1",
        friendly_name="M",
        hardware="swan-x",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    slave_cand = {
        "speaker_device_id": "slave1",
        "friendly_name": "S",
        "hardware": "swan-y",
        "sync_group_status": "standalone",
        "connection_status": ConnectionStatus.ONLINE.value,
    }
    add_cb = MagicMock()
    device_manager.set_add_entities_callback("switch", add_cb)
    state_on = SimpleNamespace(state="on")
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[existing],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=master_dict,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_available_slave_device_dict_list",
            return_value=[slave_cand],
        ),
        patch.object(StateMachine, "get", return_value=state_on),
    ):
        await device_manager._add_or_remove_switches()
    add_cb.assert_not_called()


async def test_add_or_remove_from_slave_device_list_creates_switch(
    hass: HomeAssistant,
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "master1")}, name="M")
    slave_info = SlaveDeviceInfo(
        friendly_name="Sub",
        ssid="",
        mask=None,
        volume=0,
        mute=False,
        channel=0,
        battery=None,
        ip_addr="2.2.2.2",
        version="1",
        uuid="sub-uuid",
    )
    master_dict = HIVIDevice(
        speaker_device_id="master1",
        friendly_name="M",
        hardware="swan-x",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.MASTER,
        slave_device_list=[slave_info],
    ).model_dump(mode="json")
    add_cb = MagicMock()
    device_manager.set_add_entities_callback("switch", add_cb)
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=master_dict,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_available_slave_device_dict_list",
            return_value=[],
        ),
        patch.object(StateMachine, "get", return_value=None),
    ):
        await device_manager._add_or_remove_switches()
    add_cb.assert_called_once()


async def test_async_remove_entities_for_device_swallows_registry_error(
    device_manager: HIVIDeviceManager,
) -> None:
    ent_reg = MagicMock()
    ent_reg.entities.get_entries_for_device_id = MagicMock(
        side_effect=RuntimeError("registry broken")
    )
    with patch(
        "homeassistant.components.hivi_speaker.device_manager.er.async_get",
        return_value=ent_reg,
    ):
        await device_manager.async_remove_entities_for_device("d1")


async def test_update_device_entity_states_toggles_switch(
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "m")}, name="M")
    ent_on = SimpleNamespace(
        entity_id="switch.m_slave_keep",
        unique_id="m_slave_keep",
    )
    dct = HIVIDevice(
        speaker_device_id="m",
        friendly_name="M",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.MASTER,
        slave_device_list=[
            SlaveDeviceInfo(
                friendly_name="K",
                ssid="",
                mask=None,
                volume=0,
                mute=False,
                channel=0,
                battery=None,
                ip_addr="1.1.1.1",
                version="1",
                uuid="keep",
            )
        ],
    ).model_dump(mode="json")
    mock_sw = MagicMock()
    device_manager.hivi_slave_control_switch_hub.get_switch = MagicMock(
        return_value=mock_sw
    )
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[ent_on],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=dct,
        ),
    ):
        await device_manager._update_device_entity_states()
    mock_sw.on_off_switch.assert_called_with(True)


async def test_update_device_entity_states_skips_when_device_dict_missing(
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "m")}, name="M")
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[SimpleNamespace(entity_id="switch.m_slave_x", unique_id="m_slave_x")],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=None,
        ),
    ):
        await device_manager._update_device_entity_states()


async def test_update_device_entity_states_turns_switch_off_when_slave_not_in_list(
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "m")}, name="M")
    ent = SimpleNamespace(entity_id="switch.m_slave_gone", unique_id="m_slave_gone")
    dct = HIVIDevice(
        speaker_device_id="m",
        friendly_name="M",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.MASTER,
        slave_device_list=[],
    ).model_dump(mode="json")
    mock_sw = MagicMock()
    device_manager.hivi_slave_control_switch_hub.get_switch = MagicMock(
        return_value=mock_sw
    )
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[ent],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=dct,
        ),
    ):
        await device_manager._update_device_entity_states()
    mock_sw.on_off_switch.assert_called_once_with(False)


async def test_update_device_entity_states_logs_when_hub_has_no_switch(
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "m")}, name="M")
    ent = SimpleNamespace(entity_id="switch.m_slave_x", unique_id="m_slave_x")
    dct = HIVIDevice(
        speaker_device_id="m",
        friendly_name="M",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.MASTER,
        slave_device_list=[
            SlaveDeviceInfo(
                friendly_name="K",
                ssid="",
                mask=None,
                volume=0,
                mute=False,
                channel=0,
                battery=None,
                ip_addr="1.1.1.1",
                version="1",
                uuid="x",
            )
        ],
    ).model_dump(mode="json")
    device_manager.hivi_slave_control_switch_hub.get_switch = MagicMock(
        return_value=None
    )
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[ent],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=dct,
        ),
    ):
        await device_manager._update_device_entity_states()


async def test_device_offline_process_marks_offline_and_signals(
    device_manager: HIVIDeviceManager,
) -> None:
    old_seen = datetime.now(tz=UTC) - timedelta(seconds=DEVICE_OFFLINE_THRESHOLD + 50)
    dct = HIVIDevice(
        speaker_device_id="old",
        friendly_name="Old",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
        last_seen=old_seen,
    ).model_dump(mode="json")
    ha_dev = SimpleNamespace(id="d-old", identifiers={(DOMAIN, "old")}, name="Old")
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=dct,
        ),
        patch(
            "homeassistant.components.hivi_speaker.device_manager.async_dispatcher_send"
        ) as mock_send,
    ):
        await device_manager._device_offline_process()
    mock_send.assert_called_once()
    assert mock_send.call_args[0][1] == SIGNAL_DEVICE_STATUS_UPDATED


async def test_device_offline_process_skips_when_device_dict_missing(
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d-miss", identifiers={(DOMAIN, "x")}, name="X")
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=None,
        ),
        patch(
            "homeassistant.components.hivi_speaker.device_manager.async_dispatcher_send"
        ) as mock_send,
    ):
        await device_manager._device_offline_process()
    mock_send.assert_not_called()


async def test_add_or_remove_switches_calls_platform_callback(
    hass: HomeAssistant,
    device_manager: HIVIDeviceManager,
) -> None:
    ha_dev = SimpleNamespace(id="d1", identifiers={(DOMAIN, "master1")}, name="M")
    master_dict = HIVIDevice(
        speaker_device_id="master1",
        friendly_name="M",
        hardware="swan-x",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
    ).model_dump(mode="json")
    slave_cand = {
        "speaker_device_id": "slave1",
        "friendly_name": "S",
        "hardware": "swan-y",
        "sync_group_status": "standalone",
        "connection_status": ConnectionStatus.ONLINE.value,
    }
    add_cb = MagicMock()
    device_manager.set_add_entities_callback("switch", add_cb)
    with (
        patch.object(
            device_manager,
            "_get_devices_for_device",
            new_callable=AsyncMock,
            return_value=[ha_dev],
        ),
        patch.object(
            device_manager,
            "_get_entities_for_device",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_device_dict_by_ha_device_id",
            return_value=master_dict,
        ),
        patch.object(
            device_manager.device_data_registry,
            "get_available_slave_device_dict_list",
            return_value=[slave_cand],
        ),
        patch.object(StateMachine, "get", return_value=None),
    ):
        await device_manager._add_or_remove_switches()
    add_cb.assert_called_once()
    assert add_cb.call_args[0][0]


async def test_async_cleanup_await_worker_cancelled_error(
    device_manager: HIVIDeviceManager,
) -> None:
    device_manager.discovery_scheduler.async_stop = AsyncMock()
    device_manager.group_coordinator.async_stop = AsyncMock()
    device_manager.device_data_registry.async_shutdown = AsyncMock()
    device_manager._unsub_discovery = None
    fut = asyncio.get_running_loop().create_future()
    fut.cancel()
    device_manager._handle_discovery_worker = fut
    await device_manager.async_cleanup()
    assert device_manager._handle_discovery_worker is None


async def test_save_discovered_warns_when_register_returns_no_id(
    device_manager: HIVIDeviceManager,
) -> None:
    device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    device_manager.async_register_device = AsyncMock(return_value="")
    device_manager.device_data_registry.set_device_dict_by_ha_device_id = MagicMock()
    await device_manager._save_discovered_devices(
        [{"UDN": "uuid:new", "friendly_name": "X", "ip_addr": "192.168.1.2"}]
    )
    device_manager.device_data_registry.set_device_dict_by_ha_device_id.assert_not_called()


def test_suggest_area_bedroom_and_bathroom(device_manager: HIVIDeviceManager) -> None:
    assert device_manager._suggest_area_from_name("Bedroom speaker") == "bed room"
    assert device_manager._suggest_area_from_name("bathroom echo") == "bathroom"
