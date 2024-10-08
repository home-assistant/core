"""The tests for the Rfxtrx cover platform."""

from unittest.mock import call

import pytest

from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError

from .conftest import create_rfx_test_cfg

from tests.common import MockConfigEntry, mock_restore_cache


async def test_one_cover(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 1 cover."""
    entry_data = create_rfx_test_cfg(devices={"0b1400cd0213c7f20d010f51": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.lightwaverf_siemens_0213c7_242")
    assert state

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.lightwaverf_siemens_0213c7_242"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.lightwaverf_siemens_0213c7_242"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.lightwaverf_siemens_0213c7_242"},
        blocking=True,
    )

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\n\x14\x00\x00\x02\x13\xc7\xf2\x0f\x00\x00")),
        call(bytearray(b"\n\x14\x00\x00\x02\x13\xc7\xf2\r\x00\x00")),
        call(bytearray(b"\n\x14\x00\x00\x02\x13\xc7\xf2\x0e\x00\x00")),
    ]


@pytest.mark.parametrize("state", ["open", "closed"])
async def test_state_restore(hass: HomeAssistant, rfxtrx, state) -> None:
    """State restoration."""

    entity_id = "cover.lightwaverf_siemens_0213c7_242"

    mock_restore_cache(hass, [State(entity_id, state)])

    entry_data = create_rfx_test_cfg(devices={"0b1400cd0213c7f20d010f51": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == state


async def test_several_covers(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 3 covers."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0b1400cd0213c7f20d010f51": {},
            "0A1400ADF394AB010D0060": {},
            "09190000009ba8010100": {},
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.lightwaverf_siemens_0213c7_242")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "LightwaveRF, Siemens 0213c7:242"

    state = hass.states.get("cover.lightwaverf_siemens_f394ab_1")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "LightwaveRF, Siemens f394ab:1"

    state = hass.states.get("cover.rollertrol_009ba8_1")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "RollerTrol 009ba8:1"


async def test_discover_covers(hass: HomeAssistant, rfxtrx_automatic) -> None:
    """Test with discovery of covers."""
    rfxtrx = rfxtrx_automatic

    await rfxtrx.signal("0a140002f38cae010f0070")
    state = hass.states.get("cover.lightwaverf_siemens_f38cae_1")
    assert state
    assert state.state == "open"

    await rfxtrx.signal("0a1400adf394ab020e0060")
    state = hass.states.get("cover.lightwaverf_siemens_f394ab_2")
    assert state
    assert state.state == "open"


async def test_duplicate_cover(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 2 duplicate covers."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0b1400cd0213c7f20d010f51": {},
            "0b1400cd0213c7f20d010f50": {},
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.lightwaverf_siemens_0213c7_242")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "LightwaveRF, Siemens 0213c7:242"


async def test_rfy_cover(hass: HomeAssistant, rfxtrx) -> None:
    """Test Rfy venetian blind covers."""
    entry_data = create_rfx_test_cfg(
        devices={
            "071a000001020301": {
                "venetian_blind_mode": "Unknown",
            },
            "0c1a0000010203010000000000": {
                "venetian_blind_mode": "Unknown",
            },
            "0c1a0000010203020000000000": {"venetian_blind_mode": "US"},
            "0c1a0000010203030000000000": {"venetian_blind_mode": "EU"},
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # Test a blind with no venetian mode setting
    state = hass.states.get("cover.rfy_010203_1")
    assert state

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.rfy_010203_1"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.rfy_010203_1"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.rfy_010203_1"},
        blocking=True,
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "cover",
            "open_cover_tilt",
            {"entity_id": "cover.rfy_010203_1"},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "cover",
            "close_cover_tilt",
            {"entity_id": "cover.rfy_010203_1"},
            blocking=True,
        )

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\x0c\x1a\x00\x00\x01\x02\x03\x01\x00\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x01\x01\x02\x03\x01\x01\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x02\x01\x02\x03\x01\x03\x00\x00\x00\x00")),
    ]

    # Test a blind with venetian mode set to US
    state = hass.states.get("cover.rfy_010203_2")
    assert state
    rfxtrx.transport.send.mock_calls = []

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.rfy_010203_2"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.rfy_010203_2"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.rfy_010203_2"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "open_cover_tilt",
        {"entity_id": "cover.rfy_010203_2"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "close_cover_tilt",
        {"entity_id": "cover.rfy_010203_2"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "stop_cover_tilt",
        {"entity_id": "cover.rfy_010203_2"},
        blocking=True,
    )

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\x0c\x1a\x00\x00\x01\x02\x03\x02\x00\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x01\x01\x02\x03\x02\x0f\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x02\x01\x02\x03\x02\x10\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x03\x01\x02\x03\x02\x11\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x04\x01\x02\x03\x02\x12\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x00\x01\x02\x03\x02\x00\x00\x00\x00\x00")),
    ]

    # Test a blind with venetian mode set to EU
    state = hass.states.get("cover.rfy_010203_3")
    assert state
    rfxtrx.transport.send.mock_calls = []

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.rfy_010203_3"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.rfy_010203_3"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.rfy_010203_3"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "open_cover_tilt",
        {"entity_id": "cover.rfy_010203_3"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "close_cover_tilt",
        {"entity_id": "cover.rfy_010203_3"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "stop_cover_tilt",
        {"entity_id": "cover.rfy_010203_3"},
        blocking=True,
    )

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\x0c\x1a\x00\x00\x01\x02\x03\x03\x00\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x01\x01\x02\x03\x03\x11\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x02\x01\x02\x03\x03\x12\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x03\x01\x02\x03\x03\x0f\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x04\x01\x02\x03\x03\x10\x00\x00\x00\x00")),
        call(bytearray(b"\x0c\x1a\x00\x00\x01\x02\x03\x03\x00\x00\x00\x00\x00")),
    ]
