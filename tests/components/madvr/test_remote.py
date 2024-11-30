"""Tests for the MadVR remote entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion

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
import homeassistant.helpers.entity_registry as er

from . import setup_integration
from .const import (
    TEST_COMMAND,
    TEST_CON_ERROR,
    TEST_FAILED_CMD,
    TEST_FAILED_OFF,
    TEST_FAILED_ON,
    TEST_IMP_ERROR,
)

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
    caplog: pytest.LogCaptureFixture,
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
    caplog.clear()
    mock_madvr_client.power_off.side_effect = TEST_CON_ERROR
    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert TEST_FAILED_OFF in caplog.text

    # Test turning off with NotImplementedError
    caplog.clear()
    mock_madvr_client.power_off.side_effect = TEST_IMP_ERROR
    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert TEST_FAILED_OFF in caplog.text

    # Reset side_effect for power_off
    mock_madvr_client.power_off.side_effect = None

    # Test turning on with ConnectionError
    caplog.clear()
    mock_madvr_client.power_on.side_effect = TEST_CON_ERROR
    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert TEST_FAILED_ON in caplog.text

    # Test turning on with NotImplementedError
    caplog.clear()
    mock_madvr_client.power_on.side_effect = TEST_IMP_ERROR
    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert TEST_FAILED_ON in caplog.text


async def test_send_command(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
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
    # cover exceptions
    # Test ConnectionError
    mock_madvr_client.add_command_to_queue.side_effect = TEST_CON_ERROR
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: entity_id, ATTR_COMMAND: TEST_COMMAND},
        blocking=True,
    )
    assert TEST_FAILED_CMD in caplog.text

    # Test NotImplementedError
    mock_madvr_client.add_command_to_queue.side_effect = TEST_IMP_ERROR
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: entity_id, ATTR_COMMAND: TEST_COMMAND},
        blocking=True,
    )
    assert TEST_FAILED_CMD in caplog.text
