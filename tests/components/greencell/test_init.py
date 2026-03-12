"""Greencell integration initialization test cases."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from greencell_client.access import GreencellAccess
from greencell_client.elec_data import ElecData3Phase, ElecDataSinglePhase
import pytest

from homeassistant.components.greencell import wait_for_device_ready
from homeassistant.components.greencell.const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    GREENCELL_DISC_TOPIC,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_SERIAL_NUMBER, TEST_VOLTAGE_TOPIC

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
async def test_wait_for_device_ready_sets_event(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test wait_for_device_ready creates event and responds to MQTT."""
    unsub, event = await wait_for_device_ready(hass, TEST_SERIAL_NUMBER)

    assert isinstance(event, asyncio.Event)
    assert not event.is_set()

    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, '{"l1": 230}')
    await hass.async_block_till_done()

    assert event.is_set()
    unsub()


@pytest.mark.asyncio
async def test_wait_for_device_ready_unsubscribe(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test unsub function stops event from being set."""
    unsub, event = await wait_for_device_ready(hass, TEST_SERIAL_NUMBER)

    unsub()

    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, '{"l1": 230}')
    await hass.async_block_till_done()

    assert not event.is_set()


@pytest.mark.asyncio
async def test_async_setup_entry_mqtt_available(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setup succeeds when MQTT is available and device responds."""
    entry = create_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.wait_for_device_ready",
        return_value=(MagicMock(), MagicMock(wait=AsyncMock())),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True
    assert entry.state is ConfigEntryState.LOADED


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
    assert isinstance(runtime.access, GreencellAccess)
    assert isinstance(runtime.current_data, ElecData3Phase)
    assert isinstance(runtime.voltage_data, ElecData3Phase)
    assert isinstance(runtime.power_data, ElecDataSinglePhase)
    assert isinstance(runtime.state_data, ElecDataSinglePhase)


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
async def test_async_setup_entry_mqtt_readiness_by_broadcast(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device readiness event is set via broadcast topic."""
    caplog.set_level("DEBUG")
    entry = create_config_entry()
    entry.add_to_hass(hass)

    payload = f'{{"id": "{TEST_SERIAL_NUMBER}"}}'

    with patch("homeassistant.components.greencell.DISCOVERY_TIMEOUT", 0.5):
        setup_task = hass.async_create_task(
            hass.config_entries.async_setup(entry.entry_id)
        )

        await asyncio.sleep(0.1)
        async_fire_mqtt_message(hass, GREENCELL_DISC_TOPIC, payload)

        result = await setup_task

    assert result is True


@pytest.mark.asyncio
async def test_async_setup_entry_mqtt_invalid_json_graceful_handling(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setup entry handles invalid MQTT JSON gracefully."""
    unsub, event = await wait_for_device_ready(hass, TEST_SERIAL_NUMBER)

    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, "{INVALID JSON}")
    await hass.async_block_till_done()

    assert not event.is_set()

    unsub()
