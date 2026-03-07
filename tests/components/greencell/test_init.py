"""Greencell integration initialization tests cases."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from greencell_client.access import GreencellAccess
from greencell_client.elec_data import ElecData3Phase, ElecDataSinglePhase
import pytest

from homeassistant.components.greencell import wait_for_device_ready
from homeassistant.components.greencell.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


def create_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_NUMBER: TEST_SERIAL_NUMBER},
        entry_id="test_entry",
        title=f"Greencell {TEST_SERIAL_NUMBER}",
    )


@pytest.mark.asyncio
async def test_wait_for_device_ready_sets_event(hass: HomeAssistant) -> None:
    """Test wait_for_device_ready creates event and unsubscribe function."""
    unsub, event = wait_for_device_ready(hass, TEST_SERIAL_NUMBER, timeout=1.0)

    assert isinstance(event, asyncio.Event)
    assert not event.is_set()
    assert callable(unsub)

    unsub()


@pytest.mark.asyncio
async def test_wait_for_device_ready_unsubscribe(hass: HomeAssistant) -> None:
    """Test unsub function can be called multiple times without error."""
    unsub, _ = wait_for_device_ready(hass, TEST_SERIAL_NUMBER, timeout=1.0)

    unsub()
    unsub()


@pytest.mark.asyncio
async def test_wait_for_device_ready_event_set(hass: HomeAssistant) -> None:
    """Test event can be manually set."""
    unsub, event = wait_for_device_ready(hass, TEST_SERIAL_NUMBER, timeout=1.0)

    assert not event.is_set()
    event.set()
    assert event.is_set()

    unsub()


@pytest.mark.asyncio
async def test_async_setup_entry_mqtt_available(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setup succeeds when MQTT is available."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True


@pytest.mark.asyncio
async def test_async_setup_entry_creates_runtime_data(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setup creates proper runtime_data structure."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    runtime = entry.runtime_data
    assert runtime is not None
    assert hasattr(runtime, "access")
    assert hasattr(runtime, "current_data")
    assert hasattr(runtime, "voltage_data")
    assert hasattr(runtime, "power_data")
    assert hasattr(runtime, "state_data")


@pytest.mark.asyncio
async def test_async_setup_entry_forwards_to_sensor_platform(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setup forwards entry to sensor platform."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True


@pytest.mark.asyncio
async def test_async_setup_entry_mqtt_not_available(
    hass: HomeAssistant,
) -> None:
    """Test setup fails when MQTT is not available."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.mqtt.is_connected",
        return_value=False,
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is False


@pytest.mark.asyncio
async def test_async_unload_entry_success(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test unload entry cleans up platforms."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_fails(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test unload entry fails if platform unload fails."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is False


@pytest.mark.asyncio
async def test_runtime_data_access_key_type(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test runtime_data access field has correct type."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert isinstance(entry.runtime_data.access, GreencellAccess)


@pytest.mark.asyncio
async def test_runtime_data_elec_data_types(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test runtime_data elec data objects have correct types."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert isinstance(entry.runtime_data.current_data, ElecData3Phase)
    assert isinstance(entry.runtime_data.voltage_data, ElecData3Phase)
    assert isinstance(entry.runtime_data.power_data, ElecDataSinglePhase)
    assert isinstance(entry.runtime_data.state_data, ElecDataSinglePhase)


@pytest.mark.asyncio
async def test_async_setup_entry_mqtt_message_handling(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setup entry handles MQTT messages correctly."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True

    discovery_topic = f"greencell/evse/{TEST_SERIAL_NUMBER}/discovery"
    test_payload = '{"id": "' + TEST_SERIAL_NUMBER + '"}'

    async_fire_mqtt_message(hass, discovery_topic, test_payload)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_async_setup_entry_mqtt_invalid_message(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setup entry handles invalid MQTT messages gracefully."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True

    discovery_topic = f"greencell/evse/{TEST_SERIAL_NUMBER}/discovery"
    invalid_payload = "{INVALID JSON}"

    async_fire_mqtt_message(hass, discovery_topic, invalid_payload)
    await hass.async_block_till_done()
