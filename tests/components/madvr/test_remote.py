"""Tests for the MadVR remote entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration
from .const import TEST_CON_ERROR, TEST_IMP_ERROR

from tests.common import MockConfigEntry, snapshot_platform


async def test_remote_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
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

    # cover exception cases
    with patch("homeassistant.components.madvr.remote._LOGGER.error") as mock_error_log:
        # Test turning off with ConnectionError

        mock_madvr_client.power_off.side_effect = TEST_CON_ERROR
        await hass.services.async_call(
            REMOTE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_error_log.assert_called_once_with(
            "Failed to turn off device %s", TEST_CON_ERROR
        )
        mock_error_log.reset_mock()

        # Test turning off with NotImplementedError
        mock_madvr_client.power_off.side_effect = TEST_IMP_ERROR
        await hass.services.async_call(
            REMOTE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_error_log.assert_called_once_with(
            "Failed to turn off device %s", TEST_IMP_ERROR
        )
        mock_error_log.reset_mock()

        # Reset side_effect for power_off
        mock_madvr_client.power_off.side_effect = None

        # Test turning on with ConnectionError
        mock_madvr_client.power_on.side_effect = TEST_CON_ERROR
        await hass.services.async_call(
            REMOTE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_error_log.assert_called_once_with(
            "Failed to turn on device %s", TEST_CON_ERROR
        )
        mock_error_log.reset_mock()

        # Test turning on with NotImplementedError
        mock_madvr_client.power_on.side_effect = TEST_IMP_ERROR
        await hass.services.async_call(
            REMOTE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_error_log.assert_called_once_with(
            "Failed to turn on device %s", TEST_IMP_ERROR
        )


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
        "send_command",
        {ATTR_ENTITY_ID: entity_id, "command": "test"},
        blocking=True,
    )

    mock_madvr_client.add_command_to_queue.assert_called_once_with(["test"])
    # cover exceptions
    with patch("homeassistant.components.madvr.remote._LOGGER.error") as mock_error_log:
        # Test ConnectionError
        mock_madvr_client.add_command_to_queue.side_effect = TEST_CON_ERROR
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "send_command",
            {ATTR_ENTITY_ID: entity_id, "command": "test"},
            blocking=True,
        )
        mock_error_log.assert_called_once_with(
            "Failed to send command %s", TEST_CON_ERROR
        )
        mock_error_log.reset_mock()

        # Test NotImplementedError
        TEST_IMP_ERROR = NotImplementedError("Not implemented")
        mock_madvr_client.add_command_to_queue.side_effect = TEST_IMP_ERROR
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "send_command",
            {ATTR_ENTITY_ID: entity_id, "command": "test"},
            blocking=True,
        )
        mock_error_log.assert_called_once_with(
            "Failed to send command %s", TEST_IMP_ERROR
        )
