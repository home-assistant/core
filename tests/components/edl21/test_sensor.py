"""Test EDL21 sensor."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.edl21.const import (
    CONF_LIMIT_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


@pytest.fixture
def sml_protocol() -> Generator[MagicMock]:
    """Mock SmlProtocol, capturing the registered telegram listener."""
    with (
        patch("homeassistant.components.edl21.sensor.SmlProtocol") as protocol_mock,
        patch("homeassistant.components.edl21.sensor.SmlGetListResponse", dict),
    ):
        protocol_instance = MagicMock()
        protocol_instance.connect = AsyncMock()
        protocol_instance._impl = MagicMock()
        protocol_instance._impl._disconnect = AsyncMock()
        protocol_mock.return_value = protocol_instance
        yield protocol_mock


def _get_listener(protocol_mock: MagicMock):
    return protocol_mock.return_value.add_listener.call_args_list[0][0][0]


def _message(*telegrams: dict) -> dict:
    """Build a fake SmlGetListResponse (patched to plain dict)."""
    return {"serverId": "0001020304050607", "valList": list(telegrams)}


def _telegram(value: float) -> dict:
    return {"objName": "1-0:16.7.0*255", "value": value, "unit": "W"}


def _energy_telegram(value: float) -> dict:
    return {"objName": "1-0:1.8.0*255", "value": value, "unit": "Wh"}


def _get_state(hass: HomeAssistant, entity_id: str) -> State:
    """Return the current state of an entity, asserting it exists."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def _get_entity_id(
    hass: HomeAssistant, entry: MockConfigEntry, obis_fragment: str
) -> str:
    """Return the entity id of the sensor matching an OBIS fragment."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    return next(
        registry_entity.entity_id
        for registry_entity in entries
        if obis_fragment in registry_entity.unique_id
    )


async def _get_power_entity_id(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Return the entity id of the sum active instantaneous power sensor."""
    return await _get_entity_id(hass, entry, "16.7")


async def _setup_entry(
    hass: HomeAssistant,
    sml_protocol: MagicMock,
    data: dict,
    options: dict | None = None,
) -> MockConfigEntry:
    """Create and set up a config entry, return it."""
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_every_update_forwarded_by_default(
    hass: HomeAssistant, sml_protocol: MagicMock
) -> None:
    """Test that without an update interval every telegram is forwarded."""
    entry = await _setup_entry(hass, sml_protocol, {CONF_SERIAL_PORT: "/dev/ttyUSB1"})
    listener = _get_listener(sml_protocol)
    entity_id: str | None = None

    for value in (100, 200, 300):
        listener(_message(_telegram(value)))
        await hass.async_block_till_done()
        entity_id = entity_id or await _get_power_entity_id(hass, entry)
        assert _get_state(hass, entity_id).state == str(value)


async def test_update_interval_throttles_telegrams(
    hass: HomeAssistant, sml_protocol: MagicMock
) -> None:
    """Test that at most one telegram per update interval is forwarded."""
    entry = await _setup_entry(
        hass,
        sml_protocol,
        {CONF_SERIAL_PORT: "/dev/ttyUSB1", CONF_UPDATE_INTERVAL: 10},
    )
    listener = _get_listener(sml_protocol)

    with patch("homeassistant.components.edl21.sensor.time") as mock_time:
        # Start the clock high enough to dominate the throttle window.
        clock = [1000.0]
        mock_time.monotonic.side_effect = lambda: clock[0]

        # First telegram always passes (and registers the sensor).
        listener(_message(_telegram(100)))
        await hass.async_block_till_done()
        entity_id = await _get_power_entity_id(hass, entry)
        assert _get_state(hass, entity_id).state == "100"

        # Inside the throttle window the update is held back.
        clock[0] = 1005.0
        listener(_message(_telegram(200)))
        await hass.async_block_till_done()
        assert _get_state(hass, entity_id).state == "100"

        # After the interval the next telegram is forwarded.
        clock[0] = 1010.0
        listener(_message(_telegram(300)))
        await hass.async_block_till_done()
        assert _get_state(hass, entity_id).state == "300"


async def test_update_interval_zero_forwards_every_telegram(
    hass: HomeAssistant, sml_protocol: MagicMock
) -> None:
    """Test that an update interval of 0 forwards every telegram."""
    entry = await _setup_entry(
        hass,
        sml_protocol,
        {
            CONF_SERIAL_PORT: "/dev/ttyUSB1",
            CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
        },
    )
    listener = _get_listener(sml_protocol)

    with patch("homeassistant.components.edl21.sensor.time") as mock_time:
        clock = [0.0]
        mock_time.monotonic.side_effect = lambda: clock[0]

        for value in (100, 100.5, 101):
            clock[0] += 0.5
            listener(_message(_telegram(value)))
            await hass.async_block_till_done()
            entity_id = await _get_power_entity_id(hass, entry)
            assert _get_state(hass, entity_id).state == str(value)


async def test_options_override_data_interval(
    hass: HomeAssistant, sml_protocol: MagicMock
) -> None:
    """Test that the options flow interval overrides the config data interval."""
    entry = await _setup_entry(
        hass,
        sml_protocol,
        {CONF_SERIAL_PORT: "/dev/ttyUSB1", CONF_UPDATE_INTERVAL: 10},
        options={CONF_UPDATE_INTERVAL: 60},
    )
    listener = _get_listener(sml_protocol)

    with patch("homeassistant.components.edl21.sensor.time") as mock_time:
        clock = [1000.0]
        mock_time.monotonic.side_effect = lambda: clock[0]

        # First telegram always passes (and registers the sensor).
        listener(_message(_telegram(100)))
        await hass.async_block_till_done()
        entity_id = await _get_power_entity_id(hass, entry)
        assert _get_state(hass, entity_id).state == "100"

        # 5 s later: inside the 60 s window from the options flow.
        clock[0] = 1005.0
        listener(_message(_telegram(200)))
        await hass.async_block_till_done()
        assert _get_state(hass, entity_id).state == "100"

        # 30 s after the first telegram: still inside the options interval.
        # With the stale data interval (10 s) this would have been forwarded.
        clock[0] = 1030.0
        listener(_message(_telegram(300)))
        await hass.async_block_till_done()
        assert _get_state(hass, entity_id).state == "100"


async def test_unload_disconnects_the_meter(
    hass: HomeAssistant, sml_protocol: MagicMock
) -> None:
    """Test that unloading the entry closes the pysml connection."""
    entry = await _setup_entry(hass, sml_protocol, {CONF_SERIAL_PORT: "/dev/ttyUSB1"})

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert sml_protocol.return_value._impl._disconnect.await_count == 1


async def test_options_change_reloads_and_reconnects(
    hass: HomeAssistant, sml_protocol: MagicMock
) -> None:
    """Test that saving options reloads the entry without a zombie connection.

    Regression test: the old pysml connection used to survive the reload and
    kept dispatching every telegram, defeating the update interval.
    """
    entry = await _setup_entry(hass, sml_protocol, {CONF_SERIAL_PORT: "/dev/ttyUSB1"})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LIMIT_INTERVAL: True, CONF_UPDATE_INTERVAL: 30},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL] == 30
    # The update listener reloaded the entry: one disconnect of the old
    # connection, a second connect for the reloaded one.
    assert sml_protocol.return_value.connect.await_count == 2
    assert sml_protocol.return_value._impl._disconnect.await_count == 1


async def test_update_interval_throttles_obis_streams_independently(
    hass: HomeAssistant, sml_protocol: MagicMock
) -> None:
    """Test that interleaved telegrams keep every OBIS stream updating."""
    entry = await _setup_entry(
        hass,
        sml_protocol,
        {CONF_SERIAL_PORT: "/dev/ttyUSB1", CONF_UPDATE_INTERVAL: 10},
    )
    listener = _get_listener(sml_protocol)

    with patch("homeassistant.components.edl21.sensor.time") as mock_time:
        clock = [1000.0]
        mock_time.monotonic.side_effect = lambda: clock[0]

        # Registration consumes each stream's throttle window.
        listener(_message(_energy_telegram(100)))
        await hass.async_block_till_done()
        clock[0] = 1001.0
        listener(_message(_telegram(1000)))
        await hass.async_block_till_done()

        energy_entity = await _get_entity_id(hass, entry, "1.8.0")
        power_entity = await _get_entity_id(hass, entry, "16.7")
        assert _get_state(hass, energy_entity).state == "100"
        assert _get_state(hass, power_entity).state == "1000"

        # Inside the window both streams are held back.
        clock[0] = 1005.0
        listener(_message(_energy_telegram(101)))
        await hass.async_block_till_done()
        assert _get_state(hass, energy_entity).state == "100"

        # Each stream unlocks on its own schedule.
        clock[0] = 1010.0
        listener(_message(_energy_telegram(102)))
        await hass.async_block_till_done()
        assert _get_state(hass, energy_entity).state == "102"

        # The power stream is one second behind and still gets its own
        # update; a telegram-wide throttle would drop it and leave the
        # power sensor stale.
        clock[0] = 1012.0
        listener(_message(_telegram(1100)))
        await hass.async_block_till_done()
        assert _get_state(hass, power_entity).state == "1100"
