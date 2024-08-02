"""Test the swiss_public_transport service."""

import json
import logging
from unittest.mock import AsyncMock, patch

from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import pytest
from voluptuous import error as vol_er

from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
    DOMAIN,
    SENSOR_CONNECTIONS_MAX,
    SERVICE_FETCH_CONNECTIONS,
)
from homeassistant.components.swiss_public_transport.helper import unique_id_from_config
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry, load_fixture

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
    ("limit", "config_data", "raise_error"),
    [
        # Happy case
        (0, MOCK_DATA_STEP_BASE, None),
        (1, MOCK_DATA_STEP_BASE, None),
        (2, MOCK_DATA_STEP_BASE, None),
        (3, MOCK_DATA_STEP_BASE, None),
        # Errors
        (-1, MOCK_DATA_STEP_BASE, None),
        (SENSOR_CONNECTIONS_MAX + 1, MOCK_DATA_STEP_BASE, None),
        (10, MOCK_DATA_STEP_BASE, OpendataTransportConnectionError()),
        (11, MOCK_DATA_STEP_BASE, OpendataTransportError()),
    ],
)
async def test_service_call_fetch_connections(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    limit,
    config_data,
    raise_error,
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
        mock().connections = json.loads(load_fixture("connections.json", DOMAIN))[
            0:limit
        ]

        # Setup the config entry
        unique_id = unique_id_from_config(config_entry.data)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        entity_id = entity_registry.entities.get_entity_id(
            (
                Platform.SENSOR,
                DOMAIN,
                f"{unique_id}_departure",
            )
        )
        assert entity_registry.async_is_registered(entity_id)

        assert hass.services.has_service(DOMAIN, SERVICE_FETCH_CONNECTIONS)
        mock().async_get_data.side_effect = raise_error
        try:
            response = await hass.services.async_call(
                domain=DOMAIN,
                service=SERVICE_FETCH_CONNECTIONS,
                service_data={ATTR_ENTITY_ID: entity_id, "limit": limit},
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()
            _LOGGER.info(response)
            assert response[entity_id]
            assert len(response[entity_id]["connections"]) == limit
        except vol_er.MultipleInvalid:
            assert limit in [-1, 16]
        except HomeAssistantError:
            assert limit in [10]
        except UpdateFailed:
            assert limit in [11]
