"""Test Mikrotik setup process."""
from datetime import timedelta
from itertools import cycle

from homeassistant import config_entries
from homeassistant.components import mikrotik
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from . import DEVICE_3_WIRELESS, ENTRY_DATA, HUB1_WIRELESS_DATA, OLD_ENTRY_CONFIG
from .test_hub import DATA_RETURN, setup_mikrotik_integration

from tests.async_mock import AsyncMock, patch
from tests.common import MockConfigEntry


async def test_setup_with_no_config(hass, api):
    """Test that we do not discover anything or try to set up a hub."""
    assert await async_setup_component(hass, mikrotik.DOMAIN, {})
    assert mikrotik.DOMAIN not in hass.data


async def test_successful_config_entry(hass, api):
    """Test config entry successful setup."""
    mikrotik_mock = await setup_mikrotik_integration(hass)
    assert mikrotik_mock.config_entry.state == config_entries.ENTRY_STATE_LOADED


async def test_old_config_entry(hass, api):
    """Test converting  old config entry successfully."""
    mikrotik_mock = await setup_mikrotik_integration(hass, entry_data=OLD_ENTRY_CONFIG)
    assert mikrotik_mock.config_entry.state == config_entries.ENTRY_STATE_LOADED


async def test_config_fail_setup(hass, api):
    """Test that a failed setup will not store the config."""
    with patch.object(mikrotik, "Mikrotik") as mock_integration:
        mock_integration.return_value.async_setup.return_value = AsyncMock(
            return_value=False
        )

        config_entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=dict(ENTRY_DATA))
        config_entry.add_to_hass(hass)

        await setup_mikrotik_integration(hass, config_entry=config_entry)

    assert config_entry.state == config_entries.ENTRY_STATE_SETUP_ERROR


async def test_unload_entry(hass, api):
    """Test being able to unload an entry."""
    mikrotik_mock = await setup_mikrotik_integration(hass)
    assert mikrotik_mock.config_entry.state == config_entries.ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(mikrotik_mock.config_entry.entry_id)
    assert mikrotik_mock.config_entry.state == config_entries.ENTRY_STATE_NOT_LOADED


async def test_successfull_integration_setup(hass, api):
    """Test successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        mikrotik_mock = await setup_mikrotik_integration(hass)

        assert forward_entry_setup.mock_calls[0][1] == (
            mikrotik_mock.config_entry,
            "device_tracker",
        )

        assert len(mikrotik_mock.hubs) == len(ENTRY_DATA[mikrotik.CONF_HUBS])
        assert mikrotik_mock.option_detection_time == timedelta(
            seconds=mikrotik.DEFAULT_DETECTION_TIME
        )
        assert (
            mikrotik_mock.signal_data_update
            == f"{mikrotik.DOMAIN}-{mikrotik_mock.config_entry.entry_id}-data-updated"
        )
        assert (
            mikrotik_mock.signal_new_clients
            == f"{mikrotik.DOMAIN}-{mikrotik_mock.config_entry.entry_id}-new-clients"
        )
        assert (
            mikrotik_mock.signal_options_update
            == f"{mikrotik.DOMAIN}-{mikrotik_mock.config_entry.entry_id}-options-updated"
        )


async def test_updating_clients(hass, api):
    """Test scheduled update for all clients."""
    i = cycle([0, 1])
    hub_index = 0

    def mock_command(self, cmd, params=None):
        nonlocal i
        nonlocal hub_index

        # check for first cmd by each hub and set hub_index accordingly
        if cmd in [
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IDENTITY],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP],
        ]:
            hub_index = next(i)
        return DATA_RETURN[cmd][hub_index]

    with patch.object(mikrotik.hub.MikrotikHub, "command", new=mock_command), patch(
        "homeassistant.components.mikrotik.async_dispatcher_send"
    ) as mock_disptacher:

        mikrotik_mock = await setup_mikrotik_integration(hass, support_wireless=True)
        assert len(mock_disptacher.mock_calls) == 3

        # new data_update signal is sent if no new device is detected
        assert len(mikrotik_mock.clients) == 2
        await mikrotik_mock.async_update()
        await hass.async_block_till_done()

        assert len(mikrotik_mock.clients) == 2
        assert len(mock_disptacher.mock_calls) == 4

        # new data_update and new_clients signal is sent if new devices are detected
        HUB1_WIRELESS_DATA.append(DEVICE_3_WIRELESS)
        await mikrotik_mock.async_update()
        await hass.async_block_till_done()
        assert len(mikrotik_mock.clients) == 3
        assert len(mock_disptacher.mock_calls) == 6

    # revert the changes made for this test
    del HUB1_WIRELESS_DATA[1]


async def test_restoring_devices(hass, api):
    """Test restoring existing device_tracker from entity registry."""
    config_entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=ENTRY_DATA)
    config_entry.add_to_hass(hass)

    registry = await entity_registry.async_get_registry(hass)
    registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        mikrotik.DOMAIN,
        "00:00:00:00:00:01",
        suggested_object_id="device_1",
        config_entry=config_entry,
    )
    registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        mikrotik.DOMAIN,
        "00:00:00:00:00:02",
        suggested_object_id="device_2",
        config_entry=config_entry,
    )
    registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        mikrotik.DOMAIN,
        "00:00:00:00:00:04",
        suggested_object_id="device_4",
        config_entry=config_entry,
    )

    await setup_mikrotik_integration(hass, support_wireless=True)

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "home"

    # test device_4 which is not in wireless list is restored
    device_4 = hass.states.get("device_tracker.device_4")
    assert device_4 is not None
    assert device_4.state == "not_home"
