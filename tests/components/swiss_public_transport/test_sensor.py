"""Test the swiss_public_transport service."""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
    DOMAIN,
    SERVICE_FETCH_CONNECTIONS,
)
from homeassistant.components.swiss_public_transport.helper import unique_id_from_config
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

MOCK_DATA_STEP_BASE = {
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


@pytest.mark.parametrize(
    ("limit", "config_data"),
    [
        # (0, MOCK_DATA_STEP_BASE),
        (1, MOCK_DATA_STEP_BASE),
        # (SENSOR_CONNECTIONS_MAX + 1, MOCK_DATA_STEP_BASE),
    ],
)
async def test_service_call_fetch_connections(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    limit,
    config_data,
) -> None:
    """Test service call."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        title=f"Service test call with limit={limit}",
        unique_id=unique_id_from_config(config_data),
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

        assert hass.services.has_service(DOMAIN, SERVICE_FETCH_CONNECTIONS)
        response = await hass.services.async_call(
            domain=DOMAIN,
            service=SERVICE_FETCH_CONNECTIONS,
            service_data={"limit": limit, "entity_id": config_entry.entry_id},
            blocking=True,
            return_response=True,
        )
        await hass.async_block_till_done()
        assert response
