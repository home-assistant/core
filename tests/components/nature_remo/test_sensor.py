"""Tests for the Nature Remo sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aionatureremo import (
    Appliance,
    Device,
    NatureRemoConnectionError,
    NatureRemoRateLimitError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nature_remo.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import async_poll

from tests.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    snapshot_platform,
)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Snapshot every entity and registry entry the integration creates."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_sensors_unavailable_on_update_failure(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed poll marks sensors unavailable."""
    mock_client.get_devices.side_effect = NatureRemoConnectionError("refused")
    await async_poll(hass, freezer)

    state = hass.states.get("sensor.living_remo_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_rate_limit_defers_the_next_poll_until_the_reset(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A 429 naming a reset time skips the polls the API would reject anyway."""
    # The next poll runs one interval from now; a reset two intervals past
    # that leaves exactly one regular poll inside the rate-limited window.
    reset = dt_util.utcnow() + 3 * UPDATE_INTERVAL
    mock_client.get_appliances.side_effect = NatureRemoRateLimitError(
        429, "limited", reset=int(reset.timestamp())
    )
    await async_poll(hass, freezer)

    state = hass.states.get("sensor.living_remo_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    polls = mock_client.get_devices.call_count

    await async_poll(hass, freezer)
    assert mock_client.get_devices.call_count == polls

    await async_poll(hass, freezer)
    assert mock_client.get_devices.call_count == polls + 1


@pytest.mark.parametrize(
    "reset_offset",
    [None, -UPDATE_INTERVAL],
    ids=["no_reset", "past_reset"],
)
async def test_rate_limit_without_a_usable_reset_keeps_polling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    reset_offset: timedelta | None,
) -> None:
    """A 429 without a future reset is an ordinary failed poll.

    A reset already behind us must not become the next update interval:
    a zero or negative delay would poll in a tight loop.
    """
    reset = (
        int((dt_util.utcnow() + reset_offset).timestamp())
        if reset_offset is not None
        else None
    )
    mock_client.get_appliances.side_effect = NatureRemoRateLimitError(
        429, "limited", reset=reset
    )
    await async_poll(hass, freezer)

    state = hass.states.get("sensor.living_remo_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    polls = mock_client.get_devices.call_count

    await async_poll(hass, freezer)
    assert mock_client.get_devices.call_count == polls + 1


async def test_offline_device_sensors_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    devices: list[Device],
) -> None:
    """A hub reporting online=False serves no readings; None keeps serving.

    ``online`` only exists on newer firmware, so the Remo mini fixture
    (no flag at all, parsed as None) must stay available.
    """
    mock_client.get_devices.return_value = [
        replace(device, online=False) if device.id == "device-remo3-1" else device
        for device in devices
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.living_remo_temperature").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.living_remo_humidity").state == STATE_UNAVAILABLE

    mini = hass.states.get("sensor.bedroom_remo_mini_temperature")
    assert mini is not None
    assert mini.state != STATE_UNAVAILABLE


async def test_sensors_unavailable_when_the_hub_disappears(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    devices: list[Device],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A hub the API stops reporting leaves its sensors unavailable."""
    mock_client.get_devices.return_value = [
        device for device in devices if device.id != "device-remo3-1"
    ]
    await async_poll(hass, freezer)

    state = hass.states.get("sensor.living_remo_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_smart_meter_follows_the_hub_reading_it(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    devices: list[Device],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A meter goes unavailable while its Remo E reports itself offline.

    The cloud keeps serving the readings it collected before the hub went
    away, so without following the hub the meter would look live with
    stale values.
    """
    assert hass.states.get("sensor.smart_meter_power").state != STATE_UNAVAILABLE

    mock_client.get_devices.return_value = [
        replace(device, online=False) if device.id == "device-remoe-1" else device
        for device in devices
    ]
    await async_poll(hass, freezer)

    assert hass.states.get("sensor.smart_meter_power").state == STATE_UNAVAILABLE


async def test_smart_meter_unavailable_when_its_hub_disappears(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    devices: list[Device],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A meter whose hub drops out of the account stops reporting.

    The appliance keeps its cached readings in the API response, so
    without following the hub the meter would look live.
    """
    mock_client.get_devices.return_value = [
        device for device in devices if device.id != "device-remoe-1"
    ]
    await async_poll(hass, freezer)

    assert hass.states.get("sensor.smart_meter_power").state == STATE_UNAVAILABLE


async def test_smart_meter_reading_dropout_is_unknown(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    appliances: list[Appliance],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A meter that stops publishing properties reads unknown, not stale."""
    mock_client.get_appliances.return_value = [
        replace(appliance, smart_meter=None)
        if appliance.id == "appliance-meter-1"
        else appliance
        for appliance in appliances
    ]
    await async_poll(hass, freezer)

    assert hass.states.get("sensor.smart_meter_power").state == STATE_UNKNOWN


async def test_smart_meter_without_reverse_direction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A meter without EPC 227 (no solar) gets no exported-energy sensor."""
    payloads = await async_load_json_array_fixture(hass, "appliances.json", DOMAIN)
    for payload in payloads:
        if payload["id"] == "appliance-meter-1":
            payload["smart_meter"]["echonetlite_properties"] = [
                prop
                for prop in payload["smart_meter"]["echonetlite_properties"]
                if prop["epc"] != 227
            ]
    mock_client.get_appliances.return_value = [
        Appliance.from_dict(item) for item in payloads
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.smart_meter_imported_energy") is not None
    assert hass.states.get("sensor.smart_meter_exported_energy") is None
