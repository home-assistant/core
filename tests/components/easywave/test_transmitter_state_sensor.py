"""Tests for the Easywave transmitter state-sensor entities."""

from unittest.mock import AsyncMock, MagicMock, patch

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
