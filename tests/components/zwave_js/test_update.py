"""Test the Z-Wave JS update entities."""
from datetime import timedelta

from homeassistant.components.update.const import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.util import datetime as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

UPDATE_ENTITY = "update.z_wave_js_device_configs_update"


async def test_config_update_entity(
    hass,
    client,
):
    """Test update entity."""
    client.async_send_command.return_value = {
        "updateAvailable": False,
    }

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.attributes[ATTR_INSTALLED_VERSION] == "unknown"
    assert state.attributes[ATTR_LATEST_VERSION] == "unknown"
    assert state.state == STATE_OFF

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {
        "updateAvailable": True,
        "newVersion": "1.0.0",
    }

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.attributes[ATTR_INSTALLED_VERSION] == "unknown"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"
    assert state.state == STATE_ON

    client.async_send_command.reset_mock()
    client.async_send_command.side_effect = (
        {
            "success": True,
        },
        {"updateAvailable": False},
    )

    # Test successful update call
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_ENTITY_ID: UPDATE_ENTITY,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "driver.install_config_update"
    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "driver.check_for_config_updates"

    client.async_send_command.reset_mock()
