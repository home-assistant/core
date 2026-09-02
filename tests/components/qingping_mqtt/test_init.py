"""Test the qingping_mqtt integration setup."""

from homeassistant.components.qingping_mqtt.const import DOMAIN, MQTT_TOPIC_PREFIX
from homeassistant.components.qingping_mqtt.coordinator import QingpingMqttCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant

from . import MQTT_MAC, MQTT_TLV_PAYLOAD

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


def _mock_config_entry() -> MockConfigEntry:
    """Return a config entry for an MQTT connected device."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MQTT_MAC,
        data={CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"},
    )


async def test_setup_and_unload(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the coordinator receives device messages and the entry unloads."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: QingpingMqttCoordinator = entry.runtime_data
    assert coordinator.data["online"] is True

    async_fire_mqtt_message(
        hass, f"{MQTT_TOPIC_PREFIX}/{MQTT_MAC}/up", MQTT_TLV_PAYLOAD
    )
    await hass.async_block_till_done()

    assert coordinator.data["sensors"]["temperature"] == 25.8
    assert coordinator.data["sensors"]["humidity"] == 65.3

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_mqtt_not_configured(hass: HomeAssistant) -> None:
    """Test the entry retries setup when the MQTT integration is missing."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
