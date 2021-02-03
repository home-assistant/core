"""Test integration initialization."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.ozw import DOMAIN, PLATFORMS, const

from .common import setup_ozw

from tests.common import MockConfigEntry


async def test_init_entry(hass, generic_data):
    """Test setting up config entry."""
    await setup_ozw(hass, fixture=generic_data)

    # Verify integration + platform loaded.
    assert "ozw" in hass.config.components
    for platform in PLATFORMS:
        assert platform in hass.config.components, platform
        assert f"{platform}.{DOMAIN}" in hass.config.components, f"{platform}.{DOMAIN}"

    # Verify services registered
    assert hass.services.has_service(DOMAIN, const.SERVICE_ADD_NODE)
    assert hass.services.has_service(DOMAIN, const.SERVICE_REMOVE_NODE)


async def test_setup_entry_without_mqtt(hass):
    """Test setting up config entry without mqtt integration setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenZWave",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_publish_without_mqtt(hass, caplog):
    """Test publish without mqtt integration setup."""
    with patch("homeassistant.components.ozw.OZWOptions") as ozw_options:
        await setup_ozw(hass)

        send_message = ozw_options.call_args[1]["send_message"]

        mqtt_entries = hass.config_entries.async_entries("mqtt")
        mqtt_entry = mqtt_entries[0]
        await hass.config_entries.async_remove(mqtt_entry.entry_id)
        await hass.async_block_till_done()

        assert not hass.config_entries.async_entries("mqtt")

        # Sending a message should not error with the MQTT integration not set up.
        send_message("test_topic", "test_payload")

    assert "MQTT integration is not set up" in caplog.text


async def test_unload_entry(hass, generic_data, switch_msg, caplog):
    """Test unload the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
    )
    entry.add_to_hass(hass)
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED

    receive_message = await setup_ozw(hass, entry=entry, fixture=generic_data)

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
    await setup_ozw(hass, entry=entry, fixture=generic_data)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ENTRY_STATE_LOADED
    assert len(hass.states.async_entity_ids("switch")) == 1
    for record in caplog.records:
        assert record.levelname != "ERROR"


async def test_remove_entry(hass, stop_addon, uninstall_addon, caplog):
    """Test remove the config entry."""
    # test successful remove without created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        data={"integration_created_addon": False},
    )
    entry.add_to_hass(hass)
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    # test successful remove with created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        data={"integration_created_addon": True},
    )
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    stop_addon.call_count == 1
    uninstall_addon.call_count == 1
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    stop_addon.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on stop failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    stop_addon.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    stop_addon.call_count == 1
    uninstall_addon.call_count == 0
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to stop the OpenZWave add-on" in caplog.text
    stop_addon.side_effect = None
    stop_addon.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on uninstall failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    uninstall_addon.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    stop_addon.call_count == 1
    uninstall_addon.call_count == 1
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to uninstall the OpenZWave add-on" in caplog.text


async def test_setup_entry_with_addon(hass, get_addon_discovery_info):
    """Test set up entry using OpenZWave add-on."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenZWave",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        data={"use_addon": True},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.ozw.MQTTClient", autospec=True) as mock_client:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_client.return_value.start_client.call_count == 1

    # Verify integration + platform loaded.
    assert "ozw" in hass.config.components
    for platform in PLATFORMS:
        assert platform in hass.config.components, platform
        assert f"{platform}.{DOMAIN}" in hass.config.components, f"{platform}.{DOMAIN}"

    # Verify services registered
    assert hass.services.has_service(DOMAIN, const.SERVICE_ADD_NODE)
    assert hass.services.has_service(DOMAIN, const.SERVICE_REMOVE_NODE)


async def test_setup_entry_without_addon_info(hass, get_addon_discovery_info):
    """Test set up entry using OpenZWave add-on but missing discovery info."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenZWave",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        data={"use_addon": True},
    )
    entry.add_to_hass(hass)

    get_addon_discovery_info.return_value = None

    with patch("homeassistant.components.ozw.MQTTClient", autospec=True) as mock_client:
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert mock_client.return_value.start_client.call_count == 0
    assert entry.state == config_entries.ENTRY_STATE_SETUP_RETRY


async def test_unload_entry_with_addon(
    hass, get_addon_discovery_info, generic_data, switch_msg, caplog
):
    """Test unload the config entry using the OpenZWave add-on."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenZWave",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        data={"use_addon": True},
    )
    entry.add_to_hass(hass)

    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED

    with patch("homeassistant.components.ozw.MQTTClient", autospec=True) as mock_client:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_client.return_value.start_client.call_count == 1
    assert entry.state == config_entries.ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
