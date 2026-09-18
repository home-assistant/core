"""Test the Nina init file."""

from typing import Any
from unittest.mock import AsyncMock

from pynina import ApiError

from homeassistant.components.nina.const import (
    CONF_AREA_FILTER,
    CONF_FILTER_CORONA,
    CONF_FILTERS,
    CONF_HEADLINE_FILTER,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.common import MockConfigEntry

ENTRY_DATA: dict[str, Any] = {
    CONF_MESSAGE_SLOTS: 5,
    CONF_REGIONS: {"083350000000": "Aach, Stadt"},
    CONF_FILTERS: {
        CONF_HEADLINE_FILTER: ".*corona.*",
        CONF_AREA_FILTER: ".*",
    },
}


async def test_config_migration_from1_1(
    hass: HomeAssistant,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the migration to a new configuration layout."""
    old_entry_data: dict[str, Any] = {
        CONF_MESSAGE_SLOTS: 5,
        CONF_FILTER_CORONA: True,
        CONF_REGIONS: {"083350000000": "Aach, Stadt"},
    }

    old_conf_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN, title="NINA", data=old_entry_data, version=1
    )

    old_conf_entry.add_to_hass(hass)

    await setup_platform(hass, old_conf_entry, mock_nina_class, nina_warnings)

    assert dict(old_conf_entry.data) == ENTRY_DATA
    assert old_conf_entry.state is ConfigEntryState.LOADED
    assert old_conf_entry.version == 1
    assert old_conf_entry.minor_version == 3


async def test_config_migration_from1_2(
    hass: HomeAssistant,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the migration to a new configuration layout with sections."""
    old_entry_data: dict[str, Any] = {
        CONF_MESSAGE_SLOTS: 5,
        CONF_HEADLINE_FILTER: ".*corona.*",
        CONF_AREA_FILTER: ".*",
        CONF_REGIONS: {"083350000000": "Aach, Stadt"},
    }

    old_conf_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN, title="NINA", data=old_entry_data, version=1, minor_version=2
    )

    old_conf_entry.add_to_hass(hass)

    await setup_platform(hass, old_conf_entry, mock_nina_class, nina_warnings)

    assert dict(old_conf_entry.data) == ENTRY_DATA
    assert old_conf_entry.state is ConfigEntryState.LOADED
    assert old_conf_entry.version == 1
    assert old_conf_entry.minor_version == 3


async def test_config_migration_downgrade(
    hass: HomeAssistant,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the migration to an old version."""

    conf_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN, title="NINA", data=ENTRY_DATA, version=2
    )

    conf_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(conf_entry.entry_id)
    await hass.async_block_till_done()

    assert dict(conf_entry.data) == ENTRY_DATA
    assert conf_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_sensors_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA sensors with no connected."""
    mock_nina_class.update.side_effect = ApiError("Could not connect to Api")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
