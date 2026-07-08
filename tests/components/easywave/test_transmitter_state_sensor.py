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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_ID,
    MOCK_GATEWAY_TITLE,
    MOCK_TRANSMITTER_SERIAL,
    _device_subentry_data,
    _devices_options,
    _transmitter_device_record,
    async_setup_easywave_entry,
)

from tests.common import MockConfigEntry

MOCK_DEVICE_ID = f"transmitter_{MOCK_TRANSMITTER_SERIAL}"


def _make_gateway(extra_data: dict[str, object]) -> MockConfigEntry:
    """Return a gateway entry with a transmitter device using given data."""
    subentry_data = _transmitter_device_record(
        title="Test Transmitter",
        button_count=int(extra_data.get(CONF_BUTTON_COUNT, 4)),
        switch_mode=str(extra_data.get(CONF_SWITCH_MODE, TRANSMITTER_SWITCH_IMPULSE)),
        grouping_mode=str(
            extra_data.get(CONF_GROUPING_MODE, TRANSMITTER_GROUPING_GROUP)
        ),
    )
    data = dict(subentry_data["data"])
    data.update(extra_data)
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(
            _device_subentry_data(
                subentry_data["unique_id"], subentry_data["title"], data
            )
        ),
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
    assert entry.config_subentry_id is None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "b"

    assert await hass.config_entries.async_unload(gateway.entry_id)
    await hass.async_block_till_done()
