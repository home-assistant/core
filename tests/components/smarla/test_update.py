"""Test update platform for Swing2Sleep Smarla integration."""

from unittest.mock import MagicMock, patch

from pysmarlaapi.federwiege.services.types import UpdateStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import setup_integration, update_property_listeners

from tests.common import MockConfigEntry, snapshot_platform

UPDATE_ENTITY_ID = "update.smarla_firmware"


@pytest.mark.usefixtures("mock_federwiege")
async def test_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the smarla update platform."""
    with patch("homeassistant.components.smarla.PLATFORMS", [Platform.UPDATE]):
        assert await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_update_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
) -> None:
    """Test smarla update initial state and behavior when an update gets available."""
    assert await setup_integration(hass, mock_config_entry)

    state = hass.states.get(UPDATE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"

    mock_federwiege.check_firmware_update.return_value = ("1.1.0", "")
    await async_update_entity(hass, UPDATE_ENTITY_ID)
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LATEST_VERSION] == "1.1.0"


async def test_update_install(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
) -> None:
    """Test the smarla update install action."""
    mock_federwiege.check_firmware_update.return_value = ("1.1.0", "")
    assert await setup_integration(hass, mock_config_entry)

    mock_update_property = mock_federwiege.get_property("system", "firmware_update")

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: UPDATE_ENTITY_ID},
        blocking=True,
    )

    mock_update_property.set.assert_called_once_with(1)


@pytest.mark.parametrize("status", [UpdateStatus.DOWNLOADING, UpdateStatus.INSTALLING])
async def test_update_in_progress(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    status: UpdateStatus,
) -> None:
    """Test the smarla update progress."""
    assert await setup_integration(hass, mock_config_entry)

    mock_update_status_property = mock_federwiege.get_property(
        "system", "firmware_update_status"
    )

    state = hass.states.get(UPDATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_IN_PROGRESS] is False

    mock_update_status_property.get.return_value = status
    await update_property_listeners(mock_update_status_property)
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_IN_PROGRESS] is True


async def test_update_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
) -> None:
    """Test smarla update unknown behavior."""
    assert await setup_integration(hass, mock_config_entry)

    state = hass.states.get(UPDATE_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN

    mock_federwiege.check_firmware_update.return_value = None
    await async_update_entity(hass, UPDATE_ENTITY_ID)
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
