"""Integration lifecycle plus tightly-coupled unit tests (HA-style split elsewhere)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hivi_speaker import (
    async_remove_config_entry_device,
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.hivi_speaker.const import DOMAIN
from homeassistant.components.hivi_speaker.device import (
    ConnectionStatus,
    HIVIDevice,
    SyncGroupStatus,
)
from homeassistant.components.hivi_speaker.device_data_registry import DeviceDataRegistry
from homeassistant.components.hivi_speaker.discovery_scheduler import parse_ssdp_response
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a config entry for tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HiVi Speaker",
        data={},
    )


async def test_setup_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry: device manager is created and platforms are loaded."""
    config_entry.add_to_hass(hass)

    mock_device_manager = AsyncMock()
    mock_device_manager.async_setup = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.hivi_speaker.HIVIDeviceManager",
            return_value=mock_device_manager,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_forward_setups,
    ):
        result = await async_setup_entry(hass, config_entry)

    assert result is True
    mock_device_manager.async_setup.assert_awaited_once()
    mock_forward_setups.assert_awaited_once_with(config_entry, ["switch"])

    assert DOMAIN in hass.data
    assert config_entry.entry_id in hass.data[DOMAIN]
    assert (
        hass.data[DOMAIN][config_entry.entry_id]["device_manager"]
        is mock_device_manager
    )


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_unload_entry: device manager is cleaned up and entry data removed."""
    config_entry.add_to_hass(hass)

    mock_device_manager = AsyncMock()
    mock_device_manager.async_cleanup = AsyncMock(return_value=None)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_unload_platforms:
        result = await async_unload_entry(hass, config_entry)

    assert result is True
    mock_device_manager.async_cleanup.assert_awaited_once()
    mock_unload_platforms.assert_awaited_once_with(config_entry, ["switch"])
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_unload_entry_no_device_manager(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_unload_entry when device_manager is missing (e.g. partial cleanup)."""
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {}

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await async_unload_entry(hass, config_entry)

    assert result is True
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_async_remove_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_remove_entry clears device registry loop and removes storage."""
    config_entry.add_to_hass(hass)
    mock_reg = MagicMock()
    mock_reg.devices = {}

    with (
        patch(
            "homeassistant.components.hivi_speaker.dr.async_get",
            return_value=mock_reg,
        ),
        patch(
            "homeassistant.helpers.storage.Store.async_remove",
            new_callable=AsyncMock,
        ) as mock_store_remove,
    ):
        await async_remove_entry(hass, config_entry)

    mock_store_remove.assert_awaited_once()


async def test_async_remove_entry_removes_devices_linked_to_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Devices tied to this config entry are removed from the device registry."""
    config_entry.add_to_hass(hass)
    linked = SimpleNamespace(
        id="dev-linked",
        config_entries={config_entry.entry_id},
    )
    other = SimpleNamespace(
        id="dev-other",
        config_entries={"some.other.entry"},
    )
    legacy = SimpleNamespace(
        id="dev-legacy",
        config_entries=None,
        config_entry_id=config_entry.entry_id,
    )
    mock_reg = MagicMock()
    mock_reg.devices = {"a": linked, "b": other, "c": legacy}

    with (
        patch(
            "homeassistant.components.hivi_speaker.dr.async_get",
            return_value=mock_reg,
        ),
        patch(
            "homeassistant.helpers.storage.Store.async_remove",
            new_callable=AsyncMock,
        ),
    ):
        await async_remove_entry(hass, config_entry)

    removed = {c.args[0] for c in mock_reg.async_remove_device.call_args_list}
    assert removed == {"dev-linked", "dev-legacy"}


async def test_unload_entry_platform_unload_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_unload_entry when async_unload_platforms returns False."""
    config_entry.add_to_hass(hass)
    mock_device_manager = AsyncMock()
    mock_device_manager.async_cleanup = AsyncMock(return_value=None)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ):
        result = await async_unload_entry(hass, config_entry)

    assert result is False
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_remove_config_entry_device_not_our_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test device removal hook returns False when identifiers are not DOMAIN."""
    config_entry.add_to_hass(hass)
    device = SimpleNamespace(identifiers={("mqtt", "other")})

    result = await async_remove_config_entry_device(hass, config_entry, device)

    assert result is False


async def test_remove_config_entry_device_no_device_manager(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test device removal allows HA delete when device_manager is missing."""
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {}
    device = SimpleNamespace(
        id="ha-device-1",
        identifiers={(DOMAIN, "udn-1")},
    )

    result = await async_remove_config_entry_device(hass, config_entry, device)

    assert result is True


async def test_remove_config_entry_device_with_manager(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test device removal cleans entities, registry data, and control switches."""
    config_entry.add_to_hass(hass)
    mock_dm = MagicMock()
    mock_dm.async_remove_entities_for_device = AsyncMock()
    mock_dm.device_data_registry = MagicMock()
    mock_dm.device_data_registry.get_device_dict_by_ha_device_id = MagicMock(
        return_value={
            "speaker_device_id": "spk-udn",
            "friendly_name": "Spk",
            "ha_device_id": "ha-device-1",
        }
    )
    mock_dm.device_data_registry.async_remove_device_data = AsyncMock()
    mock_dm.remove_control_entities_by_speaker_device_id = AsyncMock()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_dm,
    }
    device = SimpleNamespace(
        id="ha-device-1",
        identifiers={(DOMAIN, "udn-1")},
    )

    result = await async_remove_config_entry_device(hass, config_entry, device)

    assert result is True
    mock_dm.async_remove_entities_for_device.assert_awaited_once_with("ha-device-1")
    mock_dm.device_data_registry.async_remove_device_data.assert_awaited_once_with(
        "ha-device-1"
    )
    mock_dm.remove_control_entities_by_speaker_device_id.assert_awaited_once_with(
        "spk-udn"
    )


async def test_unload_entry_device_manager_cleanup_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """async_cleanup exception is logged; unload still follows unload_ok path."""
    config_entry.add_to_hass(hass)
    mock_device_manager = AsyncMock()
    mock_device_manager.async_cleanup = AsyncMock(side_effect=RuntimeError("cleanup failed"))
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await async_unload_entry(hass, config_entry)

    assert result is True


async def test_unload_entry_async_unload_platforms_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Exception from async_unload_platforms sets unload_ok False."""
    config_entry.add_to_hass(hass)
    mock_device_manager = AsyncMock()
    mock_device_manager.async_cleanup = AsyncMock(return_value=None)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        side_effect=RuntimeError("unload failed"),
    ):
        result = await async_unload_entry(hass, config_entry)

    assert result is False


async def test_unload_entry_hass_data_pop_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Exception while popping hass.data is swallowed; unload_ok still returned."""

    class PopRaises(dict):
        def pop(self, key, default=None):
            raise RuntimeError("pop failed")

    config_entry.add_to_hass(hass)
    mock_device_manager = AsyncMock()
    mock_device_manager.async_cleanup = AsyncMock(return_value=None)
    domain_bucket = PopRaises()
    domain_bucket[config_entry.entry_id] = {"device_manager": mock_device_manager}
    hass.data[DOMAIN] = domain_bucket

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await async_unload_entry(hass, config_entry)

    assert result is True


async def test_async_remove_entry_device_registry_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Registry cleanup failure is logged; storage remove still attempted."""
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.hivi_speaker.dr.async_get",
            side_effect=RuntimeError("registry boom"),
        ),
        patch(
            "homeassistant.helpers.storage.Store.async_remove",
            new_callable=AsyncMock,
        ) as mock_store_remove,
    ):
        await async_remove_entry(hass, config_entry)

    mock_store_remove.assert_awaited_once()


async def test_async_remove_entry_store_remove_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Storage remove failure is logged."""
    config_entry.add_to_hass(hass)
    mock_reg = MagicMock()
    mock_reg.devices = {}

    with (
        patch(
            "homeassistant.components.hivi_speaker.dr.async_get",
            return_value=mock_reg,
        ),
        patch(
            "homeassistant.helpers.storage.Store.async_remove",
            new_callable=AsyncMock,
            side_effect=RuntimeError("store boom"),
        ),
    ):
        await async_remove_entry(hass, config_entry)


async def test_remove_config_entry_device_inner_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Exception during cleanup still returns True (allow HA to remove device)."""
    config_entry.add_to_hass(hass)
    mock_dm = MagicMock()
    mock_dm.async_remove_entities_for_device = AsyncMock(
        side_effect=RuntimeError("remove entities failed")
    )
    mock_dm.device_data_registry = MagicMock()
    mock_dm.device_data_registry.get_device_dict_by_ha_device_id = MagicMock(
        return_value=None
    )

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_dm,
    }
    device = SimpleNamespace(
        id="ha-device-1",
        identifiers={(DOMAIN, "udn-1")},
    )

    result = await async_remove_config_entry_device(hass, config_entry, device)

    assert result is True


# --- device.py (models) ---


def test_hivid_device_unique_id_derived_from_mac() -> None:
    """model_post_init sets unique_id from mac when unique_id is empty."""
    dev = HIVIDevice(
        mac_address="aa:bb:cc:dd:ee:ff",
        unique_id="",
    )
    assert dev.unique_id == "hivi_aabbccddeeff"


def test_is_available_for_media_false_for_slave() -> None:
    """Slave + online is not available for media."""
    dev = HIVIDevice(
        sync_group_status=SyncGroupStatus.SLAVE,
        connection_status=ConnectionStatus.ONLINE,
    )
    assert dev.is_available_for_media is False


def test_can_be_slave_when_standalone_online() -> None:
    """Standalone and online can be set as slave."""
    dev = HIVIDevice(
        sync_group_status=SyncGroupStatus.STANDALONE,
        connection_status=ConnectionStatus.ONLINE,
    )
    assert dev.can_be_slave is True


# --- device_data_registry.py ---


@asynccontextmanager
async def _device_registry(hass: HomeAssistant):
    reg = DeviceDataRegistry(hass)
    try:
        yield reg
    finally:
        await reg.async_shutdown()


async def test_async_load_with_data(hass: HomeAssistant) -> None:
    """async_load restores device_data from store."""
    async with _device_registry(hass) as registry:
        with patch.object(
            registry._store,
            "async_load",
            new_callable=AsyncMock,
            return_value={
                "device_data": {"ha1": {"device_dict": {"speaker_device_id": "s1"}}},
                "version": 1,
            },
        ):
            await registry.async_load()

        assert registry.get_device_data("ha1")["device_dict"]["speaker_device_id"] == "s1"


async def test_async_load_empty(hass: HomeAssistant) -> None:
    """async_load with no store data leaves empty dict."""
    async with _device_registry(hass) as registry:
        with patch.object(
            registry._store, "async_load", new_callable=AsyncMock, return_value=None
        ):
            await registry.async_load()

        assert registry.get_device_data("any") == {}


async def test_set_get_device_data_and_schedule_save(hass: HomeAssistant) -> None:
    """set_device_data writes key and schedules save."""
    async with _device_registry(hass) as registry:
        with patch.object(registry._store, "async_delay_save") as mock_delay:
            registry.set_device_data("ha1", "k", "v")

        assert registry.get_device_data("ha1")["k"] == "v"
        mock_delay.assert_called_once()


async def test_get_connection_status_counts(hass: HomeAssistant) -> None:
    """Count online/offline from nested device_dict."""
    async with _device_registry(hass) as registry:
        registry._device_data = {
            "a": {
                "device_dict": {"connection_status": ConnectionStatus.ONLINE.value},
            },
            "b": {
                "device_dict": {"connection_status": ConnectionStatus.OFFLINE.value},
            },
        }
        online, offline = registry.get_connection_status_counts()
        assert online == 1
        assert offline == 1


async def test_set_device_dict_and_getters(hass: HomeAssistant) -> None:
    """set_device_dict_by_ha_device_id and lookup helpers."""
    async with _device_registry(hass) as registry:
        with patch.object(registry._store, "async_delay_save"):
            registry.set_device_dict_by_ha_device_id(
                "ha_x",
                {"speaker_device_id": "spk1", "friendly_name": "One"},
            )

        assert registry.get_device_dict_by_ha_device_id("ha_x")["speaker_device_id"] == "spk1"
        assert registry.get_device_dict_by_speaker_device_id("spk1")["friendly_name"] == "One"
        assert registry.get_ha_device_id_by_speaker_device_id("spk1") == "ha_x"
        assert registry.get_device_dict_by_ha_device_id("missing") is None
        assert registry.get_device_dict_by_ha_device_id("missing", default={}) == {}
        assert registry.get_device_dict_by_speaker_device_id("nope") is None


async def test_registry_data_to_save_matches_store_shape(hass: HomeAssistant) -> None:
    """_data_to_save is the payload used by Store (covers callback body)."""
    async with _device_registry(hass) as registry:
        registry._device_data = {"ha1": {"device_dict": {"speaker_device_id": "s"}}}
        assert registry._data_to_save() == {
            "device_data": {"ha1": {"device_dict": {"speaker_device_id": "s"}}},
            "version": 1,
        }


async def test_get_device_dict_by_ha_device_id_bad_device_dict_returns_default(
    hass: HomeAssistant,
) -> None:
    """Truthy ha bucket without a usable device_dict yields default."""
    async with _device_registry(hass) as registry:
        registry._device_data = {"ha_x": {"note": "no dict"}}
        assert registry.get_device_dict_by_ha_device_id("ha_x") is None
        assert registry.get_device_dict_by_ha_device_id("ha_x", default={}) == {}


async def test_get_device_dict_by_speaker_skips_empty_ha_buckets(
    hass: HomeAssistant,
) -> None:
    """Empty per-ha dicts are skipped while searching by speaker id."""
    async with _device_registry(hass) as registry:
        registry._device_data = {
            "h_empty": {},
            "h2": {"device_dict": {"speaker_device_id": "want", "friendly_name": "X"}},
        }
        d = registry.get_device_dict_by_speaker_device_id("want")
        assert d is not None
        assert d["friendly_name"] == "X"


async def test_get_ha_device_id_by_speaker_returns_none_when_unmatched(
    hass: HomeAssistant,
) -> None:
    """No matching speaker_device_id ends with None."""
    async with _device_registry(hass) as registry:
        registry._device_data = {
            "ha1": {"device_dict": {"speaker_device_id": "only-this"}},
        }
        assert registry.get_ha_device_id_by_speaker_device_id("nope") is None


async def test_get_available_slave_device_dict_list(hass: HomeAssistant) -> None:
    """List standalone+online devices; optional exclude."""
    async with _device_registry(hass) as registry:
        d_ok = {
            "speaker_device_id": "s1",
            "sync_group_status": "standalone",
            "connection_status": ConnectionStatus.ONLINE.value,
        }
        d_slave = {
            "speaker_device_id": "s2",
            "sync_group_status": "slave",
            "connection_status": ConnectionStatus.ONLINE.value,
        }
        registry._device_data = {
            "h1": {"device_dict": d_ok},
            "h2": {"device_dict": d_slave},
        }
        avail = registry.get_available_slave_device_dict_list()
        assert len(avail) == 1
        assert avail[0]["speaker_device_id"] == "s1"

        avail2 = registry.get_available_slave_device_dict_list(
            exclude_speaker_device_id="s1"
        )
        assert avail2 == []


async def test_async_remove_device_data(hass: HomeAssistant) -> None:
    """Removing known ha_device_id deletes and saves."""
    async with _device_registry(hass) as registry:
        registry._device_data = {"ha1": {"x": 1}}
        with patch.object(registry._store, "async_save", new_callable=AsyncMock) as mock_save:
            await registry.async_remove_device_data("ha1")

        assert "ha1" not in registry._device_data
        mock_save.assert_awaited_once()


async def test_device_registry_updated_remove_cleans_data(
    hass: HomeAssistant,
) -> None:
    """Bus remove event drops stored data for that ha_device_id."""
    async with _device_registry(hass) as registry:
        registry._device_data = {"dev_to_remove": {"device_dict": {}}}
        with patch.object(registry._store, "async_save", new_callable=AsyncMock):
            hass.bus.async_fire(
                "device_registry_updated",
                {"device_id": "dev_to_remove", "action": "remove"},
            )
            await hass.async_block_till_done()

        assert "dev_to_remove" not in registry._device_data


async def test_device_registry_updated_remove_unknown_device(
    hass: HomeAssistant,
) -> None:
    """Remove event for unknown id hits debug-only branch (no crash)."""
    async with _device_registry(hass) as registry:
        registry._device_data = {}
        hass.bus.async_fire(
            "device_registry_updated",
            {"device_id": "ghost", "action": "remove"},
        )
        await hass.async_block_till_done()


async def test_async_clear_all_data(hass: HomeAssistant) -> None:
    """clear_all unsubscribes and wipes data then saves."""
    async with _device_registry(hass) as registry:
        registry._device_data = {"ha1": {}}
        with patch.object(registry._store, "async_save", new_callable=AsyncMock):
            await registry.async_clear_all_data()

        assert registry._device_data == {}
        assert registry._unsub_device_registry is None


# --- discovery_scheduler (helpers, no network) ---


def test_parse_ssdp_response_parses_status_and_headers() -> None:
    """parse_ssdp_response extracts HTTP status line and known headers."""
    text = (
        "HTTP/1.1 200 OK\r\n"
        "location: http://192.168.1.10/desc.xml\r\n"
        "st: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
    )
    out = parse_ssdp_response(text, ("192.168.1.5", 1900))

    assert out["ip"] == "192.168.1.5"
    assert out["port"] == 1900
    assert "200 OK" in out.get("connection_status", "")
    assert out.get("location") == "http://192.168.1.10/desc.xml"
    assert "st" in out
