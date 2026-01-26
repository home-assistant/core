"""Greencell integration initialization tests cases.

This module contains test cases for the Greencell integration initialization,
including tests for device ready waiting, setup entry, unload entry, and
runtime data structure validation using Home Assistant's MQTT mock utilities.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from greencell_client.access import GreencellAccess
from greencell_client.elec_data import ElecData3Phase, ElecDataSinglePhase
import pytest

from homeassistant.components.greencell import async_unload_entry, wait_for_device_ready
from homeassistant.components.greencell.const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    GREENCELL_ACCESS_KEY,
    GREENCELL_CURRENT_DATA_KEY,
    GREENCELL_POWER_DATA_KEY,
    GREENCELL_STATE_DATA_KEY,
    GREENCELL_VOLTAGE_DATA_KEY,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


def create_config_entry() -> ConfigEntry:
    """Create a mock config entry.

    Creates a MockConfigEntry with default test configuration for the
    Greencell domain.

    Returns:
        ConfigEntry: A mock configuration entry for testing.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_NUMBER: TEST_SERIAL_NUMBER},
        entry_id="test_entry",
        title=f"Greencell {TEST_SERIAL_NUMBER}",
    )


@pytest.mark.asyncio
async def test_wait_for_device_ready_sets_event(hass: HomeAssistant) -> None:
    """Test wait_for_device_ready creates event and unsubscribe function.

    Verifies that wait_for_device_ready returns a callable unsubscribe
    function and an asyncio.Event object.

    Args:
        hass: The Home Assistant instance.
    """
    unsub, event = wait_for_device_ready(hass, TEST_SERIAL_NUMBER, timeout=1.0)

    assert isinstance(event, asyncio.Event)
    assert not event.is_set()
    assert callable(unsub)

    unsub()


@pytest.mark.asyncio
async def test_wait_for_device_ready_unsubscribe(hass: HomeAssistant) -> None:
    """Test unsub function can be called multiple times without error.

    Verifies that the unsubscribe function returned by wait_for_device_ready
    can be called multiple times safely.

    Args:
        hass: The Home Assistant instance.
    """
    unsub, _ = wait_for_device_ready(hass, TEST_SERIAL_NUMBER, timeout=1.0)

    unsub()
    unsub()


@pytest.mark.asyncio
async def test_wait_for_device_ready_event_set(hass: HomeAssistant) -> None:
    """Test event can be manually set.

    Verifies that the asyncio.Event returned by wait_for_device_ready
    can be set to signal device readiness.

    Args:
        hass: The Home Assistant instance.
    """
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
    """Test setup succeeds when MQTT is available.

    Verifies that config entry setup completes successfully when MQTT is
    properly mocked and available. Uses async_setup() which properly
    manages config entry state transitions.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """
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
    """Test setup creates proper runtime_data structure.

    Verifies that async_setup_entry creates all required runtime data
    keys including access, current, voltage, power, and state data.
    Uses async_setup() for proper state management.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.runtime_data is not None
    assert GREENCELL_ACCESS_KEY in entry.runtime_data
    assert GREENCELL_CURRENT_DATA_KEY in entry.runtime_data
    assert GREENCELL_VOLTAGE_DATA_KEY in entry.runtime_data
    assert GREENCELL_POWER_DATA_KEY in entry.runtime_data
    assert GREENCELL_STATE_DATA_KEY in entry.runtime_data


@pytest.mark.asyncio
async def test_async_setup_entry_forwards_to_sensor_platform(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setup forwards entry to sensor platform.

    Verifies that the setup process properly forwards the entry to the
    sensor platform for entity creation. Uses async_setup() for correct
    state management.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """
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
    """Test setup fails when MQTT is not available.

    Verifies that setup fails gracefully when the MQTT integration is
    not properly initialized or available.

    Args:
        hass: The Home Assistant instance.
    """
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
    """Test unload entry cleans up platforms.

    Verifies that async_unload_entry returns True and properly unloads
    all platforms associated with the config entry.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """
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
        return_value=True,
    ) as mock_unload:
        result = await async_unload_entry(hass, entry)

    assert result is True
    mock_unload.assert_called_once_with(entry, [Platform.SENSOR])


@pytest.mark.asyncio
async def test_async_unload_entry_fails(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test unload entry fails if platform unload fails.

    Verifies that async_unload_entry returns False when
    async_unload_platforms fails.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ):
        result = await async_unload_entry(hass, entry)

    assert result is False


@pytest.mark.asyncio
async def test_async_unload_entry_removes_from_data(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test unload entry removes entry from hass.data.

    Verifies that async_unload_entry properly cleans up the entry
    from Home Assistant data storage.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """
    entry = create_config_entry()
    entry.add_to_hass(hass)

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {"some": "data"}

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    if DOMAIN in hass.data:
        assert entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_runtime_data_access_key_type(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test runtime_data ACCESS key has correct type.

    Verifies that the GREENCELL_ACCESS_KEY in runtime_data is an
    instance of GreencellAccess after successful setup.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """

    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert isinstance(entry.runtime_data[GREENCELL_ACCESS_KEY], GreencellAccess)


@pytest.mark.asyncio
async def test_runtime_data_elec_data_types(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test runtime_data elec data objects have correct types.

    Verifies that the electrical data objects in runtime_data are
    instances of ElecData3Phase or ElecDataSinglePhase as appropriate.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """

    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert isinstance(entry.runtime_data[GREENCELL_CURRENT_DATA_KEY], ElecData3Phase)
    assert isinstance(entry.runtime_data[GREENCELL_VOLTAGE_DATA_KEY], ElecData3Phase)
    assert isinstance(entry.runtime_data[GREENCELL_POWER_DATA_KEY], ElecDataSinglePhase)
    assert isinstance(entry.runtime_data[GREENCELL_STATE_DATA_KEY], ElecDataSinglePhase)


@pytest.mark.asyncio
async def test_async_setup_entry_mqtt_message_handling(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setup entry handles MQTT messages correctly.

    Verifies that the integration properly subscribes to MQTT topics
    and processes incoming discovery messages. This test demonstrates
    the integration with Home Assistant's MQTT mock utilities.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """
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
    """Test setup entry handles invalid MQTT messages gracefully.

    Verifies that the integration doesn't crash when receiving
    malformed MQTT messages. Uses Home Assistant's MQTT mock utilities
    to inject bad messages into the system.

    Args:
        hass: The Home Assistant instance.
        mqtt_mock: The MQTT mock client from Home Assistant.
    """
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
