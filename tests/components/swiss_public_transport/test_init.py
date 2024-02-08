"""Test the swiss_public_transport config flow."""
from unittest.mock import AsyncMock, patch

from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MOCK_DATA_STEP = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
}

CONNECTIONS = [
    {
        "departure": "2024-01-06T18:03:00+0100",
        "number": 0,
        "platform": 0,
        "transfers": 0,
        "duration": "10",
        "delay": 0,
    },
    {
        "departure": "2024-01-06T18:04:00+0100",
        "number": 1,
        "platform": 1,
        "transfers": 0,
        "duration": "10",
        "delay": 0,
    },
    {
        "departure": "2024-01-06T18:05:00+0100",
        "number": 2,
        "platform": 2,
        "transfers": 0,
        "duration": "10",
        "delay": 0,
    },
]


async def test_migration_1_1_to_1_2(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test successful setup."""

    config_entry_faulty = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA_STEP,
        title="MIGRATION_TEST",
        version=1,
        minor_version=1,
    )
    config_entry_faulty.add_to_hass(hass)

    with patch(
        "homeassistant.components.swiss_public_transport.OpendataTransport",
        return_value=AsyncMock(),
    ) as mock:
        mock().connections = CONNECTIONS

        # Setup the config entry
        await hass.config_entries.async_setup(config_entry_faulty.entry_id)
        await hass.async_block_till_done()
        assert entity_registry.async_is_registered(
            entity_registry.entities.get_entity_id(
                (Platform.SENSOR, DOMAIN, "test_start test_destination_departure")
            )
        )

        # Check change in config entry
        assert config_entry_faulty.minor_version == 2
        assert config_entry_faulty.unique_id == "test_start test_destination"

        # Check "None" is gone
        assert not entity_registry.async_is_registered(
            entity_registry.entities.get_entity_id(
                (Platform.SENSOR, DOMAIN, "None_departure")
            )
        )
