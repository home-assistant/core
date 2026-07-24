"""Tests for the Easywave transmitter state-sensor entities."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from easywave_home_control.codec import ButtonFunction, ButtonPushEvent
from easywave_home_control.codec.events import EasywaveButton

from homeassistant.components.easywave.const import (
    CONF_BUTTON_COUNT,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SWITCH_MODE,
    DOMAIN,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_TRANSMITTER_SERIAL,
    _entry_with_subentries,
    _transmitter_device_record,
    async_setup_easywave_entry,
    async_stop_easywave_listener,
    mock_easywave_transceiver,
)

from tests.common import MockConfigEntry

MOCK_DEVICE_ID = f"transmitter_{MOCK_TRANSMITTER_SERIAL}"


def _make_gateway(extra_data: dict[str, object]) -> MockConfigEntry:
    """Return a gateway entry with a transmitter device using given data."""
    record = _transmitter_device_record(
        title="Test Transmitter",
        button_count=int(extra_data.get(CONF_BUTTON_COUNT, 4)),
        switch_mode=str(extra_data.get(CONF_SWITCH_MODE, TRANSMITTER_SWITCH_IMPULSE)),
        grouping_mode=str(
            extra_data.get(CONF_GROUPING_MODE, TRANSMITTER_GROUPING_GROUP)
        ),
    )
    devices = dict(record["data"][CONF_DEVICES])
    device_id = next(iter(devices))
    devices[device_id] = {**devices[device_id], **extra_data}
    return _entry_with_subentries(
        ConfigSubentryData(
            data={CONF_DEVICES: devices},
            subentry_type=record["subentry_type"],
            title=record["title"],
            unique_id=record["unique_id"],
        )
    )


async def test_last_button_sensor_restores_state(hass: HomeAssistant) -> None:
    """Last-button sensor restores last known pressed button across HA restarts."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveTransmitterLastButtonSensor,
    )

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_GROUP,
        }
    )
    mock_sensor_data = MagicMock()
    mock_sensor_data.native_value = "b"

    with patch.object(
        EasywaveTransmitterLastButtonSensor,
        "async_get_last_sensor_data",
        new=AsyncMock(return_value=mock_sensor_data),
    ):
        await async_setup_easywave_entry(hass, gateway)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_last_button"
    )
    assert entity_id is not None
    entry = registry.async_get(entity_id)
    assert entry is not None
    assert entry.config_subentry_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "b"

    assert await hass.config_entries.async_unload(gateway.entry_id)
    await hass.async_block_till_done()


async def test_sensor_setup_skips_unsupported_transmitter_types(
    hass: HomeAssistant,
) -> None:
    """Unsupported transmitter operating types do not create state sensors."""
    gateway = _make_gateway({CONF_OPERATING_TYPE: "2"})
    await async_setup_easywave_entry(hass, gateway)

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{MOCK_DEVICE_ID}_last_button")
        is None
    )
    assert (
        registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_battery_warning"
        )
        is None
    )


async def test_sensor_setup_skips_non_group_transmitters(
    hass: HomeAssistant,
) -> None:
    """Individual grouping transmitters do not create group state sensors."""
    gateway = _make_gateway({CONF_GROUPING_MODE: "individual"})
    await async_setup_easywave_entry(hass, gateway)

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{MOCK_DEVICE_ID}_last_button")
        is None
    )


async def test_battery_sensor_restores_last_known_state(hass: HomeAssistant) -> None:
    """Battery warning sensor restores the last known state across restarts."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveTransmitterBatterySensor,
    )

    gateway = _make_gateway({})
    mock_sensor_data = MagicMock()
    mock_sensor_data.native_value = "low"

    with patch.object(
        EasywaveTransmitterBatterySensor,
        "async_get_last_sensor_data",
        new=AsyncMock(return_value=mock_sensor_data),
    ):
        await async_setup_easywave_entry(hass, gateway)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_battery_warning"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "low"
    assert hass.states.get(entity_id).attributes["icon"] == "mdi:battery-alert"


async def _run_transmitter_telegram_test(
    hass: HomeAssistant,
    gateway: MockConfigEntry,
    *telegrams: object,
) -> None:
    """Deliver telegrams through the coordinator listener."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, gateway, transceiver)
    coordinator = gateway.runtime_data.coordinator
    await coordinator.suspend_telegram_listener()

    receive_calls = 0

    async def receive_side_effect(timeout: float = 30.0) -> object:
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls <= len(telegrams):
            return telegrams[receive_calls - 1]
        raise asyncio.CancelledError

    transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)
    coordinator.ensure_telegram_listener()
    await hass.async_block_till_done(wait_background_tasks=True)
    await coordinator.suspend_telegram_listener()
    await hass.async_block_till_done()


async def _teardown_transmitter_telegram_test(
    hass: HomeAssistant,
    gateway: MockConfigEntry,
) -> None:
    """Stop listener tasks and unload the config entry."""
    await async_stop_easywave_listener(hass, gateway)
    await hass.config_entries.async_unload(gateway.entry_id)
    await hass.async_block_till_done()


async def test_last_button_sensor_updates_from_telegram(
    hass: HomeAssistant,
) -> None:
    """Last-button sensor state updates when a button press telegram arrives."""
    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_GROUP,
        }
    )

    try:
        await _run_transmitter_telegram_test(
            hass,
            gateway,
            ButtonPushEvent(
                transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
                button=EasywaveButton.B,
                function=ButtonFunction.DEFAULT,
                should_ignore=False,
            ),
        )

        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_last_button"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == "b"
    finally:
        await _teardown_transmitter_telegram_test(hass, gateway)


async def test_battery_sensor_shows_low_after_low_battery_telegram(
    hass: HomeAssistant,
) -> None:
    """Battery warning sensor shows low after a low-battery telegram."""
    gateway = _make_gateway({})

    try:
        await _run_transmitter_telegram_test(
            hass,
            gateway,
            ButtonPushEvent(
                transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
                button=EasywaveButton.A,
                function=ButtonFunction.LOW_BATTERY,
                should_ignore=False,
            ),
        )

        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_battery_warning"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "low"
        assert state.attributes["icon"] == "mdi:battery-alert"
    finally:
        await _teardown_transmitter_telegram_test(hass, gateway)
