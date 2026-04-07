"""Tests for the HiVi Speaker switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.hivi_speaker.const import DOMAIN
from homeassistant.components.hivi_speaker.switch_hub import HIVISlaveControlSwitchHub
from homeassistant.core import HomeAssistant
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

    from homeassistant.components.hivi_speaker.switch import async_setup_entry

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
    from homeassistant.components.hivi_speaker.switch import HIVISlaveControlSwitch
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
    from homeassistant.components.hivi_speaker.switch import HIVISlaveControlSwitch
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
