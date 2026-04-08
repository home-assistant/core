"""Tests for the HiVi Speaker switch platform."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hivi_speaker.const import DOMAIN
from homeassistant.components.hivi_speaker.device import (
    ConnectionStatus,
    HIVIDevice,
    SlaveDeviceInfo,
    SyncGroupStatus,
)
from homeassistant.components.hivi_speaker.switch import (
    HIVISlaveControlSwitch,
    async_setup_entry,
)
from homeassistant.components.hivi_speaker.switch_hub import HIVISlaveControlSwitchHub
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import EventBus, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import MockConfigEntry


@pytest.fixture
def mock_device_manager():
    """Create a mock device manager with registry for switch tests."""
    manager = MagicMock()
    manager.device_data_registry.get_ha_device_id_by_speaker_device_id = MagicMock(
        return_value="mock-slave-ha-id"
    )
    return manager


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a config entry for tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HiVi Speaker",
        data={},
    )


async def test_switch_setup_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """Test switch async_setup_entry: device manager callback is registered."""
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    async_add_entities: AddEntitiesCallback = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)

    mock_device_manager.set_add_entities_callback.assert_called_once_with(
        "switch",
        async_add_entities,
    )


async def test_switch_entity_available_and_attributes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """Test switch entity: available and extra_state_attributes when master device exists."""
    master_id = "master-udn-1"
    slave_id = "slave-udn-2"
    master_device_dict = {
        "speaker_device_id": master_id,
        "friendly_name": "Master Speaker",
        "connection_status": "online",
        "sync_group_status": "standalone",
    }
    slave_device_dict = {
        "speaker_device_id": slave_id,
        "friendly_name": "Slave Speaker",
    }

    def get_device_dict(speaker_device_id: str):
        if speaker_device_id == master_id:
            return master_device_dict
        if speaker_device_id == slave_id:
            return slave_device_dict
        return None

    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(side_effect=get_device_dict)
    )

    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id=master_id,
        slave_speaker_device_id=slave_id,
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )

    assert switch.available is True
    attrs = switch.extra_state_attributes
    assert attrs["master_device"] == master_id
    assert attrs["slave_device"] == slave_id
    assert attrs["master_name"] == "Master Speaker"
    assert attrs["slave_name"] == "Slave Speaker"
    assert switch.unique_id == f"{master_id}_slave_{slave_id}"
    assert "Play in sync" in switch.name


async def test_switch_entity_unavailable_when_no_master(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """Test switch entity: available is False when master device is not in registry."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )

    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="missing-master",
        slave_speaker_device_id="slave-udn",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )

    assert switch.available is False
    attrs = switch.extra_state_attributes
    assert attrs["master_device"] is None
    assert attrs["master_name"] is None


async def test_switch_hub_init_and_tracks_switches(hass: HomeAssistant) -> None:
    """Exercise HIVISlaveControlSwitchHub __init__, add_switch, and get_switch."""
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi Speaker", data={})
    entry.add_to_hass(hass)

    hub = HIVISlaveControlSwitchHub(hass, entry)
    assert hub.hass is hass
    assert hub.entry is entry
    assert hub.switches == {}

    assert hub.get_switch("u1") is None

    mock_sw = MagicMock()
    mock_sw.unique_id = "u1"
    hub.add_switch(mock_sw)

    assert hub.get_switch("u1") is mock_sw
    assert hub.get_switch("missing") is None
    assert hub.switches == {"u1": mock_sw}


def _master_slave_registry_mocks(
    mock_device_manager: MagicMock,
) -> None:
    """Wire registry for master-u / slave-u device dicts."""
    slave_info = SlaveDeviceInfo(
        friendly_name="Slave",
        ssid="",
        mask=None,
        volume=0,
        mute=False,
        channel=0,
        battery=None,
        ip_addr="192.168.1.3",
        version="1",
        uuid="slave-u",
    )
    master = HIVIDevice(
        speaker_device_id="master-u",
        friendly_name="Master",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
        ip_addr="192.168.1.2",
        ssid="wifi",
        wifi_channel="6",
        auth_mode="wpa2",
        encryption_mode="aes",
        psk="x",
        uuid="muuid",
        slave_device_list=[slave_info],
    )
    master_dict = master.model_dump(mode="json")
    slave_dict = HIVIDevice(
        speaker_device_id="slave-u",
        friendly_name="Slave",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
        ip_addr="192.168.1.3",
    ).model_dump(mode="json")

    def get_by_speaker(sid: str):
        if sid == "master-u":
            return master_dict
        if sid == "slave-u":
            return slave_dict
        return None

    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(side_effect=get_by_speaker)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value="ha-slave")
    )
    mock_device_manager.postpone_discovery = AsyncMock()
    mock_device_manager.refresh_discovery = AsyncMock()


async def test_switch_async_turn_on_dispatches_group_operation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """async_turn_on sends sync_group_operation when master/slave IPs resolve."""
    _master_slave_registry_mocks(mock_device_manager)
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="master-u",
        slave_speaker_device_id="slave-u",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )

    # Entity is not added via platform; callback calls async_write_ha_state().
    with (
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_on()
        mock_send.assert_called_once()
        assert mock_send.call_args[0][1] == f"{DOMAIN}_sync_group_operation"
        operation_callback = mock_send.call_args[0][3]
        await operation_callback({"status": "accepted"})

    mock_device_manager.postpone_discovery.assert_awaited()


async def test_switch_async_turn_off_dispatches_remove_slave(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """async_turn_off sends remove_slave operation when slave IP found on master."""
    _master_slave_registry_mocks(mock_device_manager)
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="master-u",
        slave_speaker_device_id="slave-u",
        device_manager=mock_device_manager,
        create_type="from_slave_device",
    )

    with patch(
        "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
    ) as mock_send:
        await switch.async_turn_off()

    mock_send.assert_called_once()
    op_data = mock_send.call_args[0][2]
    assert op_data["type"] == "remove_slave"


async def test_switch_async_turn_on_without_master_returns_early(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """async_turn_on no-ops when master device dict is missing."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="missing-m",
        slave_speaker_device_id="slave-u",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )

    with patch(
        "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
    ) as mock_send:
        await switch.async_turn_on()

    mock_send.assert_not_called()


async def test_on_off_switch_writes_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """on_off_switch toggles _attr_is_on and requests state write when hass is set."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="m",
        slave_speaker_device_id="s",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )

    with patch.object(switch, "async_write_ha_state") as mock_write:
        switch.on_off_switch(True)
        mock_write.assert_called_once()
        switch.on_off_switch(True)
        assert mock_write.call_count == 1


def test_slave_friendly_name_from_slave_device_warns_when_master_missing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """from_slave_device + missing master logs warning; name stays empty."""

    def get_dict(sid: str):
        if sid == "master-m":
            return None
        if sid == "slave-s":
            return HIVIDevice(
                speaker_device_id="slave-s",
                friendly_name="Slave",
            ).model_dump(mode="json")
        return None

    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(side_effect=get_dict)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="master-m",
        slave_speaker_device_id="slave-s",
        device_manager=mock_device_manager,
        create_type="from_slave_device",
    )
    assert switch._slave_device_friendly_name == ""


def test_slave_friendly_name_from_slave_device_errors_when_uuid_not_in_list(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """from_slave_device: slave uuid absent from master's slave list."""
    other = SlaveDeviceInfo(
        friendly_name="Other",
        ssid="",
        mask=None,
        volume=0,
        mute=False,
        channel=0,
        battery=None,
        ip_addr="192.168.1.9",
        version="1",
        uuid="other-uuid",
    )
    master = HIVIDevice(
        speaker_device_id="master-m",
        friendly_name="Master",
        connection_status=ConnectionStatus.ONLINE,
        sync_group_status=SyncGroupStatus.STANDALONE,
        slave_device_list=[other],
    )

    def get_dict(sid: str):
        if sid == "master-m":
            return master.model_dump(mode="json")
        return None

    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(side_effect=get_dict)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="master-m",
        slave_speaker_device_id="missing-slave-uuid",
        device_manager=mock_device_manager,
        create_type="from_slave_device",
    )
    assert switch._slave_device_friendly_name == ""


def test_get_slave_ip_standalone_missing_registry_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """get_slave_device_ip_addr_by_standalone returns None when dict missing."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="m",
        slave_speaker_device_id="s",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )
    assert switch.get_slave_device_ip_addr_by_standalone() is None


def test_get_slave_ip_by_slave_master_missing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """get_slave_device_ip_addr_by_slave returns None when master dict missing."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="m",
        slave_speaker_device_id="s",
        device_manager=mock_device_manager,
        create_type="from_slave_device",
    )
    assert switch.get_slave_device_ip_addr_by_slave() is None


def test_get_slave_ip_by_slave_when_list_is_none(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """Master with slave_device_list None hits error path."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="m",
        slave_speaker_device_id="s",
        device_manager=mock_device_manager,
        create_type="from_slave_device",
    )
    switch.get_master_device = MagicMock(
        return_value=SimpleNamespace(friendly_name="M", slave_device_list=None)
    )
    assert switch.get_slave_device_ip_addr_by_slave() is None


def test_get_slave_ip_by_slave_uuid_not_in_list(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """No matching SlaveDeviceInfo in master's list."""
    info = SlaveDeviceInfo(
        friendly_name="X",
        ssid="",
        mask=None,
        volume=0,
        mute=False,
        channel=0,
        battery=None,
        ip_addr="192.168.1.2",
        version="1",
        uuid="only-this",
    )
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="m",
        slave_speaker_device_id="want-other-uuid",
        device_manager=mock_device_manager,
        create_type="from_slave_device",
    )
    switch.get_master_device = MagicMock(
        return_value=SimpleNamespace(friendly_name="M", slave_device_list=[info])
    )
    assert switch.get_slave_device_ip_addr_by_slave() is None


async def test_switch_async_added_to_hass_subscribes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """async_added_to_hass connects dispatcher and device_registry bus listener."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="m",
        slave_speaker_device_id="s",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )
    with (
        patch.object(SwitchEntity, "async_added_to_hass", new_callable=AsyncMock),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_connect"
        ) as mock_dc,
        patch.object(EventBus, "async_listen") as mock_listen,
    ):
        await switch.async_added_to_hass()

    mock_dc.assert_called_once()
    mock_listen.assert_called_once()
    assert mock_listen.call_args[0][0] == "device_registry_updated"


def test_handle_device_status_ignores_non_master_speaker(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """_handle_device_status_updated only reacts to master speaker id."""
    master_id = "master-1"
    slave_id = "slave-1"
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(
            return_value={
                "speaker_device_id": master_id,
                "connection_status": "online",
                "sync_group_status": "standalone",
            }
        )
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id=master_id,
        slave_speaker_device_id=slave_id,
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )
    with patch.object(switch, "async_write_ha_state") as mock_write:
        switch._handle_device_status_updated("other-speaker")
        mock_write.assert_not_called()
        switch._handle_device_status_updated(master_id)
        mock_write.assert_called_once()


async def test_device_registry_remove_event_triggers_switch_removal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """When slave HA device is removed, switch is popped from hub and removed."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value="ha-slave-1")
    )
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="m",
        slave_speaker_device_id="s",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )
    uid = switch._attr_unique_id
    assert uid is not None
    assert hub.switches[uid] is switch

    with patch.object(switch, "async_remove", new_callable=AsyncMock) as mock_rm:
        await switch._handle_device_registry_updated(
            SimpleNamespace(
                data={"action": "remove", "device_id": "ha-slave-1"},
            )
        )

    mock_rm.assert_awaited_once()
    assert uid not in hub.switches


async def test_async_will_remove_from_hass_unsubscribes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """async_will_remove_from_hass calls stored unsubscribe callables."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="m",
        slave_speaker_device_id="s",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )
    unsub_reg = MagicMock()
    unsub_st = MagicMock()
    switch._unsub_device_registry = unsub_reg
    switch._unsub_status = unsub_st
    await switch.async_will_remove_from_hass()
    unsub_reg.assert_called_once()
    unsub_st.assert_called_once()
    assert switch._unsub_device_registry is None
    assert switch._unsub_status is None


async def test_async_turn_off_without_master_returns_early(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """async_turn_off does not dispatch when master device is missing."""
    mock_device_manager.device_data_registry.get_device_dict_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    mock_device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id = (
        MagicMock(return_value=None)
    )
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="missing",
        slave_speaker_device_id="s",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )
    with patch(
        "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
    ) as mock_send:
        await switch.async_turn_off()
    mock_send.assert_not_called()


async def test_async_turn_on_slave_ip_missing_aborts(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """No slave IP: turn on clears is_on and does not dispatch."""
    _master_slave_registry_mocks(mock_device_manager)
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="master-u",
        slave_speaker_device_id="slave-u",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )
    with (
        patch.object(switch, "get_slave_device_ip_addr_by_standalone", return_value=None),
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_on()
    mock_send.assert_not_called()
    assert switch._attr_is_on is False


async def test_async_turn_on_master_missing_after_slave_ip(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """Second master lookup failure after slave IP resolves."""
    _master_slave_registry_mocks(mock_device_manager)
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="master-u",
        slave_speaker_device_id="slave-u",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )
    master_snapshot = switch.get_master_device()

    with (
        patch.object(
            switch,
            "get_master_device",
            side_effect=[master_snapshot, None],
        ),
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_on()
    mock_send.assert_not_called()
    assert switch._attr_is_on is False


async def test_async_turn_on_operation_callback_branches(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """Turn-on callback handles rejected, success, executing, and failure statuses."""
    _master_slave_registry_mocks(mock_device_manager)
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="master-u",
        slave_speaker_device_id="slave-u",
        device_manager=mock_device_manager,
        create_type="from_standalone_device",
    )

    with (
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_on()
        cb = mock_send.call_args[0][3]
        await cb({"status": "rejected"})
        assert switch._attr_is_on is False

    mock_device_manager.refresh_discovery.reset_mock()
    mock_device_manager.postpone_discovery.reset_mock()

    with (
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_on()
        cb = mock_send.call_args[0][3]
        await cb({"status": "executing"})
    mock_device_manager.refresh_discovery.assert_not_called()

    mock_device_manager.refresh_discovery.reset_mock()
    with (
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_on()
        cb = mock_send.call_args[0][3]
        await cb({"status": "success"})
    mock_device_manager.refresh_discovery.assert_awaited_once()

    mock_device_manager.refresh_discovery.reset_mock()
    with (
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_on()
        switch._attr_is_on = True
        cb = mock_send.call_args[0][3]
        await cb({"status": "timeout"})
    assert switch._attr_is_on is False
    mock_device_manager.refresh_discovery.assert_awaited_once()


async def test_async_turn_off_slave_ip_missing_restores_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """Turn off without slave IP restores is_on and does not dispatch."""
    _master_slave_registry_mocks(mock_device_manager)
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="master-u",
        slave_speaker_device_id="slave-u",
        device_manager=mock_device_manager,
        create_type="from_slave_device",
    )
    with (
        patch.object(switch, "get_slave_device_ip_addr_by_slave", return_value=None),
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_off()
    mock_send.assert_not_called()
    assert switch._attr_is_on is True


async def test_async_turn_off_operation_callback_branches(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_device_manager: MagicMock,
) -> None:
    """Turn-off callback handles rejected, accepted, and refresh paths."""
    _master_slave_registry_mocks(mock_device_manager)
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }
    hub = HIVISlaveControlSwitchHub(hass, config_entry)
    switch = HIVISlaveControlSwitch(
        hass=hass,
        hub=hub,
        master_speaker_device_id="master-u",
        slave_speaker_device_id="slave-u",
        device_manager=mock_device_manager,
        create_type="from_slave_device",
    )

    with (
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_off()
        cb = mock_send.call_args[0][3]
        await cb({"status": "rejected"})
        assert switch._attr_is_on is True

    mock_device_manager.postpone_discovery.reset_mock()
    mock_device_manager.refresh_discovery.reset_mock()

    with (
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_off()
        cb = mock_send.call_args[0][3]
        await cb({"status": "accepted"})
    mock_device_manager.postpone_discovery.assert_awaited()

    mock_device_manager.refresh_discovery.reset_mock()
    mock_device_manager.postpone_discovery.reset_mock()
    with (
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_off()
        cb = mock_send.call_args[0][3]
        await cb({"status": "verifying"})
    mock_device_manager.refresh_discovery.assert_not_called()
    mock_device_manager.postpone_discovery.assert_not_called()

    with (
        patch.object(switch, "async_write_ha_state"),
        patch(
            "homeassistant.components.hivi_speaker.switch.async_dispatcher_send"
        ) as mock_send,
    ):
        await switch.async_turn_off()
        cb = mock_send.call_args[0][3]
        await cb({"status": "success"})
    mock_device_manager.refresh_discovery.assert_awaited()
