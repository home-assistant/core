"""Test the swiss_public_transport integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
    CONF_TIME_FIXED,
    CONF_TIME_OFFSET,
    CONF_TIME_STATION,
    CONF_VIA,
    DOMAIN,
)
from homeassistant.components.swiss_public_transport.helper import unique_id_from_config
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MOCK_DATA_STEP_BASE = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
}

MOCK_DATA_STEP_VIA = {
    **MOCK_DATA_STEP_BASE,
    CONF_VIA: ["via_station"],
}

MOCK_DATA_STEP_TIME_FIXED = {
    **MOCK_DATA_STEP_VIA,
    CONF_TIME_FIXED: "18:03:00",
}

MOCK_DATA_STEP_TIME_OFFSET = {
    **MOCK_DATA_STEP_VIA,
    CONF_TIME_OFFSET: {"hours": 0, "minutes": 10, "seconds": 0},
    CONF_TIME_STATION: "arrival",
}

CONNECTIONS = [
    {
        "departure": "2024-01-06T18:03:00+0100",
        "number": 0,
        "platform": 0,
        "transfers": 0,
        "duration": "10",
        "delay": 0,
        "line": "T10",
    },
    {
        "departure": "2024-01-06T18:04:00+0100",
        "number": 1,
        "platform": 1,
        "transfers": 0,
        "duration": "10",
        "delay": 0,
        "line": "T10",
    },
    {
        "departure": "2024-01-06T18:05:00+0100",
        "number": 2,
        "platform": 2,
        "transfers": 0,
        "duration": "10",
        "delay": 0,
        "line": "T10",
    },
]


@pytest.mark.parametrize(
    (
        "from_version",
        "from_minor_version",
        "config_data",
        "overwrite_unique_id",
    ),
    [
        (1, 1, MOCK_DATA_STEP_BASE, "None_departure"),
        (1, 2, MOCK_DATA_STEP_BASE, None),
        (2, 1, MOCK_DATA_STEP_VIA, None),
        (3, 1, MOCK_DATA_STEP_TIME_FIXED, None),
        (3, 1, MOCK_DATA_STEP_TIME_OFFSET, None),
    ],
)
async def test_migration_from(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    from_version,
    from_minor_version,
    config_data,
    overwrite_unique_id,
) -> None:
    """Test successful setup."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        title=f"MIGRATION_TEST from {from_version}.{from_minor_version}",
        version=from_version,
        minor_version=from_minor_version,
        unique_id=overwrite_unique_id or unique_id_from_config(config_data),
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.swiss_public_transport.OpendataTransport",
        return_value=AsyncMock(),
    ) as mock:
        mock().connections = CONNECTIONS

        # Setup the config entry
        unique_id = unique_id_from_config(config_entry.data)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert entity_registry.async_is_registered(
            entity_registry.entities.get_entity_id(
                (
                    Platform.SENSOR,
                    DOMAIN,
                    f"{unique_id}_departure",
                )
            )
        )

        # Check change in config entry and verify most recent version
        assert config_entry.version == 3
        assert config_entry.minor_version == 1
        assert config_entry.unique_id == unique_id

        # Check "None" is gone from version 1.1 to 1.2
        assert not entity_registry.async_is_registered(
            entity_registry.entities.get_entity_id(
                (Platform.SENSOR, DOMAIN, "None_departure")
            )
        )


async def test_migrate_error_from_future(hass: HomeAssistant) -> None:
    """Test a future version isn't migrated."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        minor_version=1,
        unique_id="some_crazy_future_unique_id",
        data=MOCK_DATA_STEP_BASE,
    )

    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.swiss_public_transport.OpendataTransport",
        return_value=AsyncMock(),
    ) as mock:
        mock().connections = CONNECTIONS

        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
        assert entry.state is ConfigEntryState.MIGRATION_ERROR
