"""Tests for the Easywave transmitter state-sensor entities."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.easywave.const import (
    CONF_BUTTON_COUNT,
    CONF_DEVICE_DATA,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SWITCH_MODE,
    DOMAIN,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
)
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_ENTRY_DATA,
    MOCK_TRANSMITTER_SERIAL,
    _transmitter_device_record,
)

from tests.common import MockConfigEntry

MOCK_DEVICE_ID = f"transmitter_{MOCK_TRANSMITTER_SERIAL}"


def _make_gateway(extra_data: dict[str, object]) -> MockConfigEntry:
    """Return a gateway entry with a transmitter device using given data."""
    device = _transmitter_device_record(
        title="Test Transmitter",
        button_count=int(extra_data.get(CONF_BUTTON_COUNT, 4)),
        switch_mode=str(extra_data.get(CONF_SWITCH_MODE, TRANSMITTER_SWITCH_IMPULSE)),
        grouping_mode=str(
            extra_data.get(CONF_GROUPING_MODE, TRANSMITTER_GROUPING_GROUP)
        ),
    )
    device[CONF_DEVICE_DATA].update(extra_data)
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={CONF_DEVICES: [device]},
    )


def _patch_integration() -> tuple[Any, Any, Any, Any]:
    """Return patches for transceiver and coordinator."""
    mock_transceiver = MagicMock()
    mock_transceiver.is_connected = True
    mock_transceiver.usb_serial_number = "12345"
    mock_transceiver.hw_version = "1.0"
    mock_transceiver.fw_version = "2.0"
    mock_transceiver.device_path = "/dev/ttyACM0"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.async_shutdown = AsyncMock()
    mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    mock_coordinator.transceiver = mock_transceiver
    mock_coordinator.is_offline = False
    mock_coordinator.register_transmitter_entities = MagicMock()
    mock_coordinator.unregister_transmitter_entity = MagicMock()
    mock_coordinator.data = {"is_connected": True, "device_path": "/dev/ttyACM0"}

    transceiver_patch = patch(
        "homeassistant.components.easywave.RX11Transceiver",
        return_value=mock_transceiver,
    )
    coordinator_patch = patch(
        "homeassistant.components.easywave.EasywaveCoordinator",
        return_value=mock_coordinator,
    )

    return transceiver_patch, coordinator_patch, mock_transceiver, mock_coordinator


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
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    mock_sensor_data = MagicMock()
    mock_sensor_data.native_value = "b"

    t_patch, c_patch, _, _ = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveTransmitterLastButtonSensor,
            "async_get_last_sensor_data",
            new=AsyncMock(return_value=mock_sensor_data),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

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
