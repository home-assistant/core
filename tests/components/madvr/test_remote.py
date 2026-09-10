"""Tests for the MadVR remote entity."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.madvr.const import DOMAIN
from homeassistant.components.remote import (
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_COMMAND, TEST_CON_ERROR, TEST_IMP_ERROR

from tests.common import MockConfigEntry, snapshot_platform


async def test_remote_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the remote entity."""
    with patch("homeassistant.components.madvr.PLATFORMS", [Platform.REMOTE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_remote_power(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the remote entity."""

    await setup_integration(hass, mock_config_entry)

    entity_id = "remote.madvr_envy"
    remote = hass.states.get(entity_id)
    assert remote.state == STATE_ON

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    mock_madvr_client.power_off.assert_called_once()

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_madvr_client.power_on.assert_called_once()


async def test_send_command(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sending command to the remote entity."""

    await setup_integration(hass, mock_config_entry)

    entity_id = "remote.madvr_envy"
    remote = hass.states.get(entity_id)
    assert remote.state == STATE_ON

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: entity_id, ATTR_COMMAND: TEST_COMMAND},
        blocking=True,
    )

    mock_madvr_client.add_command_to_queue.assert_called_once_with([TEST_COMMAND])


@pytest.mark.parametrize("error", [TEST_CON_ERROR, TEST_IMP_ERROR])
@pytest.mark.parametrize(
    ("client_method", "service", "extra_data", "translation_key"),
    [
        ("power_off", SERVICE_TURN_OFF, {}, "power_off_failed"),
        ("power_on", SERVICE_TURN_ON, {}, "power_on_failed"),
        (
            "add_command_to_queue",
            SERVICE_SEND_COMMAND,
            {ATTR_COMMAND: TEST_COMMAND},
            "send_command_failed",
        ),
    ],
)
async def test_remote_action_failures(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    client_method: str,
    service: str,
    extra_data: dict[str, str],
    error: Exception,
    translation_key: str,
) -> None:
    """Test that failing remote actions raise HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "remote.madvr_envy"
    getattr(mock_madvr_client, client_method).side_effect = error

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **extra_data},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
