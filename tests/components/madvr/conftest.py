"""Fixtures for madVR Envy integration tests."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT
from madvr_envy.state import EnvyState

from homeassistant.components.madvr.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="madVR Envy (192.168.1.100)",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 44077,
        },
        options={},
        unique_id="madvr_192.168.1.100_44077",
    )


@pytest.fixture
def mock_envy_client() -> MagicMock:
    """Return a mocked MadvrEnvyClient."""
    client = MagicMock()
    client.host = "192.168.1.100"
    client.port = 44077
    client.logger = logging.getLogger("test.madvr_envy")

    state = EnvyState()
    state._seen_welcome = True
    state.is_on = True
    state.standby = False
    state.signal_present = True
    state.version = "1.0.0"
    state.mac_address = "00:11:22:33:44:55"
    state.tone_map_enabled = True
    state.temperatures = MagicMock(gpu=41, hdmi_input=39, cpu=44, mainboard=37)
    state.profile_groups = {"1": "Cinema"}
    state.profiles = {"1_1": "Day", "1_2": "Night"}
    state.active_profile_group = "1"
    state.active_profile_index = 2

    client.state = state
    client.connected = True

    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.wait_synced = AsyncMock()

    callback_handles: dict[str, object] = {}

    def register_adapter_callback(adapter, callback):
        callback_handles["adapter"] = callback
        return callback

    def register_callback(callback):
        callback_handles["client"] = callback

    client.register_adapter_callback = MagicMock(side_effect=register_adapter_callback)
    client.deregister_adapter_callback = MagicMock()
    client.register_callback = MagicMock(side_effect=register_callback)
    client.deregister_callback = MagicMock()

    client.tone_map_on = AsyncMock()
    client.tone_map_off = AsyncMock()
    client.standby = AsyncMock()
    client.power_off = AsyncMock()
    client.hotplug = AsyncMock()
    client.restart = AsyncMock()
    client.reload_software = AsyncMock()
    client.key_press = AsyncMock()
    client.activate_profile = AsyncMock()
    client.get_mac_address = AsyncMock()
    client.get_temperatures = AsyncMock()
    client.enum_profile_groups_collect = AsyncMock(
        return_value=[MagicMock(group_id="1", name="Cinema")]
    )
    client.enum_profiles_collect = AsyncMock(return_value=[MagicMock(profile_id="1_1", name="Day")])

    client._test_callbacks = callback_handles
    return client
