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

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)

MOCK_DATA_STEP_BASE = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
}


@pytest.mark.parametrize(
    ("limit", "config_data"),
    [
        (0, MOCK_DATA_STEP_BASE),
        (1, MOCK_DATA_STEP_BASE),
        (2, MOCK_DATA_STEP_BASE),
        (3, MOCK_DATA_STEP_BASE),
    ],
)
async def test_service_call_fetch_connections_success(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    limit,
    config_data,
) -> None:
    """Test service call with success."""

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
            0 : limit + 2
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
        response = await hass.services.async_call(
            domain=DOMAIN,
            service=SERVICE_FETCH_CONNECTIONS,
            service_data={ATTR_ENTITY_ID: entity_id, "limit": limit},
            blocking=True,
            return_response=True,
        )
        await hass.async_block_till_done()
        assert response[entity_id]
        assert len(response[entity_id]["connections"]) == limit


@pytest.mark.parametrize(
    ("limit", "config_data", "expected_result", "raise_error"),
    [
        (-1, MOCK_DATA_STEP_BASE, pytest.raises(vol_er.MultipleInvalid), None),
        (
            SENSOR_CONNECTIONS_MAX + 1,
            MOCK_DATA_STEP_BASE,
            pytest.raises(vol_er.MultipleInvalid),
            None,
        ),
        (
            1,
            MOCK_DATA_STEP_BASE,
            pytest.raises(HomeAssistantError),
            OpendataTransportConnectionError(),
        ),
        (
            2,
            MOCK_DATA_STEP_BASE,
            pytest.raises(HomeAssistantError),
            OpendataTransportError(),
        ),
    ],
)
async def test_service_call_fetch_connections_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    limit,
    config_data,
    expected_result,
    raise_error,
) -> None:
    """Test service call with standard error."""

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
        with expected_result:
            await hass.services.async_call(
                domain=DOMAIN,
                service=SERVICE_FETCH_CONNECTIONS,
                service_data={ATTR_ENTITY_ID: entity_id, "limit": limit},
                blocking=True,
                return_response=True,
            )
