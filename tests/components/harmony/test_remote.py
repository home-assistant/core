"""Test the Logitech Harmony Hub remote."""

from datetime import timedelta

from homeassistant.components.harmony.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_ON, STATE_UNAVAILABLE
from homeassistant.util import utcnow

from .const import ENTITY_REMOTE, HUB_NAME

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_connection_state_changes(
    harmony_client, mock_hc, hass, mock_write_config
):
    """Ensure connection changes are reflected in the remote state."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # mocks start with current activity == Watch TV
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)

    harmony_client.mock_disconnection()
    await hass.async_block_till_done()

    # Entities do not immediately show as unavailable
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)

    future_time = utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()
    assert hass.states.is_state(ENTITY_REMOTE, STATE_UNAVAILABLE)

    harmony_client.mock_reconnection()
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)

    harmony_client.mock_disconnection()
    harmony_client.mock_reconnection()
    future_time = utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future_time)

    await hass.async_block_till_done()
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)
