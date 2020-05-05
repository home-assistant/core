"""Test integration initialization."""
from homeassistant import config_entries
from homeassistant.components.zwave_mqtt import DOMAIN, PLATFORMS, const

from .common import setup_zwave

from tests.common import MockConfigEntry


async def test_init_entry(hass, generic_data):
    """Test setting up config entry."""
    await setup_zwave(hass, fixture=generic_data)

    # Verify integration + platform loaded.
    assert "zwave_mqtt" in hass.config.components
    for platform in PLATFORMS:
        assert platform in hass.config.components, platform
        assert f"{platform}.{DOMAIN}" in hass.config.components, f"{platform}.{DOMAIN}"

    # Verify services registered
    assert hass.services.has_service(DOMAIN, const.SERVICE_ADD_NODE)
    assert hass.services.has_service(DOMAIN, const.SERVICE_REMOVE_NODE)


async def test_unload_entry(hass, generic_data, switch_msg, caplog):
    """Test unload the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
    )
    entry.add_to_hass(hass)
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED

    receive_message = await setup_zwave(hass, entry=entry, fixture=generic_data)

    assert entry.state == config_entries.ENTRY_STATE_LOADED
    assert len(hass.states.async_entity_ids("switch")) == 1

    await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert len(hass.states.async_entity_ids("switch")) == 0

    # Send a message for a switch from the broker to check that
    # all entity topic subscribers are unsubscribed.
    receive_message(switch_msg)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("switch")) == 0

    # Load the integration again and check that there are no errors when
    # adding the entities.
    # This asserts that we have unsubscribed the entity addition signals
    # when unloading the integration previously.
    await setup_zwave(hass, entry=entry, fixture=generic_data)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ENTRY_STATE_LOADED
    assert len(hass.states.async_entity_ids("switch")) == 1
    for record in caplog.records:
        assert record.levelname != "ERROR"
