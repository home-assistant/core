"""Test the Reolink siren platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_VOLUME_LEVEL,
    DOMAIN as SIREN_DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import TEST_CAM_NAME, TEST_NVR_NAME

from tests.common import MockConfigEntry


async def test_siren(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test siren entity."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SIREN]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SIREN}.{TEST_CAM_NAME}_siren"
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # test siren turn on
    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_host.set_volume.assert_not_called()
    reolink_host.set_siren.assert_called_with(0, True, None)

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_VOLUME_LEVEL: 0.85, ATTR_DURATION: 2},
        blocking=True,
    )
    reolink_host.set_volume.assert_called_with(0, 85)
    reolink_host.set_siren.assert_called_with(0, True, 2)

    # test siren turn off
    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_host.set_siren.assert_called_with(0, False, None)


@pytest.mark.parametrize("attr", ["set_volume", "set_siren"])
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            AsyncMock(side_effect=ReolinkError("Test error")),
            HomeAssistantError,
        ),
        (
            AsyncMock(side_effect=InvalidParameterError("Test error")),
            ServiceValidationError,
        ),
    ],
)
async def test_siren_turn_on_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    attr: str,
    value: Any,
    expected: Any,
) -> None:
    """Test errors when calling siren turn on service."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SIREN]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SIREN}.{TEST_CAM_NAME}_siren"

    original = getattr(reolink_host, attr)
    setattr(reolink_host, attr, value)
    with pytest.raises(expected):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_VOLUME_LEVEL: 0.85, ATTR_DURATION: 2},
            blocking=True,
        )

    setattr(reolink_host, attr, original)


async def test_siren_turn_off_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test errors when calling siren turn off service."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SIREN]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SIREN}.{TEST_CAM_NAME}_siren"

    reolink_host.set_siren.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_host_siren(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test siren entity."""
    config_entry.is_hub = True

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SIREN]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SIREN}.{TEST_NVR_NAME}_siren"
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # test siren turn on
    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_host.set_hub_audio.assert_not_called()
    reolink_host.set_siren.assert_called_with()

    reolink_host.set_siren.reset_mock()

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_VOLUME_LEVEL: 0.85},
        blocking=True,
    )
    reolink_host.set_hub_audio.assert_called_with(alarm_volume=85)
    reolink_host.set_siren.assert_not_called()
