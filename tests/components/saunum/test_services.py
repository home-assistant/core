"""Tests for Saunum services."""

from unittest.mock import MagicMock

from pysaunum import SaunumData, SaunumException
import pytest

from homeassistant.components.saunum.const import DOMAIN
from homeassistant.components.saunum.services import (
    ATTR_DURATION,
    ATTR_FAN_DURATION,
    ATTR_TARGET_TEMPERATURE,
    SERVICE_START_SESSION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE]


async def test_start_session_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_saunum_client: MagicMock,
) -> None:
    """Test start_session service success."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_SESSION,
        {
            ATTR_ENTITY_ID: "climate.saunum_leil",
            ATTR_DURATION: 120,
            ATTR_TARGET_TEMPERATURE: 80,
            ATTR_FAN_DURATION: 10,
        },
        blocking=True,
    )

    mock_saunum_client.async_set_sauna_duration.assert_called_once_with(120)
    mock_saunum_client.async_set_target_temperature.assert_called_once_with(80)
    mock_saunum_client.async_set_fan_duration.assert_called_once_with(10)
    mock_saunum_client.async_start_session.assert_called_once()


async def test_start_session_with_defaults(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_saunum_client: MagicMock,
) -> None:
    """Test start_session service uses defaults when optional fields omitted."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_SESSION,
        {ATTR_ENTITY_ID: "climate.saunum_leil"},
        blocking=True,
    )

    # Defaults: duration=120, target_temperature=80, fan_duration=10
    mock_saunum_client.async_set_sauna_duration.assert_called_once_with(120)
    mock_saunum_client.async_set_target_temperature.assert_called_once_with(80)
    mock_saunum_client.async_set_fan_duration.assert_called_once_with(10)
    mock_saunum_client.async_start_session.assert_called_once()


async def test_start_session_door_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client: MagicMock,
    mock_saunum_data: SaunumData,
) -> None:
    """Test start_session service fails when door is open."""
    mock_saunum_client.async_get_data.return_value = SaunumData(
        **{**mock_saunum_data.__dict__, "door_open": True}
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_SESSION,
            {ATTR_ENTITY_ID: "climate.saunum_leil"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "door_open"


async def test_start_session_communication_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_saunum_client: MagicMock,
) -> None:
    """Test start_session service handles communication error."""
    mock_saunum_client.async_set_sauna_duration.side_effect = SaunumException(
        "Connection lost"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_SESSION,
            {ATTR_ENTITY_ID: "climate.saunum_leil"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "start_session_failed"
