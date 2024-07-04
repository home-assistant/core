"""The tests for the Ring button platform."""

import pytest
import ring_doorbell

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ring_client,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.SIREN)

    entry = entity_registry.async_get("siren.downstairs_siren")
    assert entry.unique_id == "123456-siren"


async def test_sirens_report_correctly(hass: HomeAssistant, mock_ring_client) -> None:
    """Tests that the initial state of a device that should be on is correct."""
    await setup_platform(hass, Platform.SIREN)

    state = hass.states.get("siren.downstairs_siren")
    assert state.attributes.get("friendly_name") == "Downstairs Siren"
    assert state.state == "unknown"


async def test_default_ding_chime_can_be_played(
    hass: HomeAssistant, mock_ring_client, mock_ring_devices
) -> None:
    """Tests the play chime request is sent correctly."""
    await setup_platform(hass, Platform.SIREN)

    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": "siren.downstairs_siren"},
        blocking=True,
    )

    await hass.async_block_till_done()

    downstairs_chime_mock = mock_ring_devices.get_device(123456)
    downstairs_chime_mock.test_sound.assert_called_once_with(kind="ding")

    state = hass.states.get("siren.downstairs_siren")
    assert state.state == "unknown"


async def test_turn_on_plays_default_chime(
    hass: HomeAssistant, mock_ring_client, mock_ring_devices
) -> None:
    """Tests the play chime request is sent correctly when turned on."""
    await setup_platform(hass, Platform.SIREN)

    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": "siren.downstairs_siren"},
        blocking=True,
    )

    await hass.async_block_till_done()

    downstairs_chime_mock = mock_ring_devices.get_device(123456)
    downstairs_chime_mock.test_sound.assert_called_once_with(kind="ding")

    state = hass.states.get("siren.downstairs_siren")
    assert state.state == "unknown"


async def test_explicit_ding_chime_can_be_played(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
) -> None:
    """Tests the play chime request is sent correctly."""
    await setup_platform(hass, Platform.SIREN)

    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": "siren.downstairs_siren", "tone": "ding"},
        blocking=True,
    )

    await hass.async_block_till_done()

    downstairs_chime_mock = mock_ring_devices.get_device(123456)
    downstairs_chime_mock.test_sound.assert_called_once_with(kind="ding")

    state = hass.states.get("siren.downstairs_siren")
    assert state.state == "unknown"


async def test_motion_chime_can_be_played(
    hass: HomeAssistant, mock_ring_client, mock_ring_devices
) -> None:
    """Tests the play chime request is sent correctly."""
    await setup_platform(hass, Platform.SIREN)

    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": "siren.downstairs_siren", "tone": "motion"},
        blocking=True,
    )

    await hass.async_block_till_done()

    downstairs_chime_mock = mock_ring_devices.get_device(123456)
    downstairs_chime_mock.test_sound.assert_called_once_with(kind="motion")

    state = hass.states.get("siren.downstairs_siren")
    assert state.state == "unknown"


@pytest.mark.parametrize(
    ("exception_type", "reauth_expected"),
    [
        (ring_doorbell.AuthenticationError, True),
        (ring_doorbell.RingTimeout, False),
        (ring_doorbell.RingError, False),
    ],
    ids=["Authentication", "Timeout", "Other"],
)
async def test_siren_errors_when_turned_on(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    exception_type,
    reauth_expected,
) -> None:
    """Tests the siren turns on correctly."""
    await setup_platform(hass, Platform.SIREN)
    config_entry = hass.config_entries.async_entries("ring")[0]

    assert not any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))

    downstairs_chime_mock = mock_ring_devices.get_device(123456)
    downstairs_chime_mock.test_sound.side_effect = exception_type

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "siren",
            "turn_on",
            {"entity_id": "siren.downstairs_siren", "tone": "motion"},
            blocking=True,
        )
    downstairs_chime_mock.test_sound.assert_called_once_with(kind="motion")
    assert (
        any(
            flow
            for flow in config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
            if flow["handler"] == "ring"
        )
        == reauth_expected
    )
