"""Test the switchbot event entities."""

from collections.abc import Callable
from unittest.mock import patch

import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.event import EventEntity
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import KEYPAD_VISION_PRO_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)


def _with_doorbell_seq(
    info: BluetoothServiceInfoBleak, seq: int = 1
) -> BluetoothServiceInfoBleak:
    """Return a BLE service info with the doorbell seq bits set."""
    mfr_data = bytearray(info.manufacturer_data[2409])
    mfr_data[12] = (mfr_data[12] & 0b11111000) | (seq & 0b00000111)
    updated_mfr_data = {2409: bytes(mfr_data)}
    return BluetoothServiceInfoBleak(
        name=info.name,
        manufacturer_data=updated_mfr_data,
        service_data=info.service_data,
        service_uuids=info.service_uuids,
        address=info.address,
        rssi=info.rssi,
        source=info.source,
        advertisement=generate_advertisement_data(
            local_name=info.name,
            manufacturer_data=updated_mfr_data,
            service_data=info.service_data,
            service_uuids=info.service_uuids,
        ),
        device=generate_ble_device(info.address, info.name),
        time=info.time,
        connectable=info.connectable,
        tx_power=info.tx_power,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_keypad_vision_pro_doorbell_event(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test keypad vision pro doorbell event uses doorbell_seq for detection."""
    triggered: list[str] = []
    original_trigger = EventEntity._trigger_event

    def _capture_trigger(
        self: EventEntity,
        event_type: str,
        event_attributes: dict | None = None,
    ) -> None:
        triggered.append(event_type)
        original_trigger(self, event_type, event_attributes)

    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, KEYPAD_VISION_PRO_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision_pro")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.switchbot.sensor.switchbot.SwitchbotKeypadVision.update",
            return_value=True,
        ),
        patch.object(EventEntity, "_trigger_event", _capture_trigger),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "event.test_name_doorbell"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNKNOWN
        assert triggered == []

        # First ring: seq changes from 0 → 1
        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 1)
        )
        await hass.async_block_till_done()
        assert triggered == ["ring"]

        # Same seq repeated — no new ring event
        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 1)
        )
        await hass.async_block_till_done()
        assert triggered == ["ring"]

        # Second ring: seq changes from 1 → 2
        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 2)
        )
        await hass.async_block_till_done()
        assert triggered == ["ring", "ring"]

        # Seq wraps from 7 → 1 — still a ring
        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 7)
        )
        await hass.async_block_till_done()
        assert triggered == ["ring", "ring", "ring"]

        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 1)
        )
        await hass.async_block_till_done()
        assert triggered == ["ring", "ring", "ring", "ring"]
