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
    ATTR_CONFIG_ENTRY_ID,
    ATTR_LIMIT,
    CONF_DESTINATION,
    CONF_START,
    CONNECTIONS_COUNT,
    CONNECTIONS_MAX,
    DOMAIN,
    SERVICE_FETCH_CONNECTIONS,
)
from homeassistant.components.swiss_public_transport.helper import unique_id_from_config
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)

MOCK_DATA_STEP_BASE = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
}


@pytest.mark.parametrize(
    ("data", "config_data"),
    [
        ({ATTR_LIMIT: 1}, MOCK_DATA_STEP_BASE),
        ({ATTR_LIMIT: 2}, MOCK_DATA_STEP_BASE),
        ({ATTR_LIMIT: 3}, MOCK_DATA_STEP_BASE),
        ({ATTR_LIMIT: CONNECTIONS_MAX}, MOCK_DATA_STEP_BASE),
        ({}, MOCK_DATA_STEP_BASE),
    ],
)
async def test_service_call_fetch_connections_success(
    hass: HomeAssistant,
    data: dict,
    config_data,
) -> None:
    """Test the fetch_connections service."""

    unique_id = unique_id_from_config(config_data)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        title=f"Service test call with data={data}",
        unique_id=unique_id,
        entry_id=f"entry_{unique_id}",
    )

    with patch(
        "homeassistant.components.swiss_public_transport.OpendataTransport",
        return_value=AsyncMock(),
    ) as mock:
        mock().connections = json.loads(load_fixture("connections.json", DOMAIN))[
            0 : data.get(ATTR_LIMIT, CONNECTIONS_COUNT) + 2
        ]

        await setup_integration(hass, config_entry)

        data[ATTR_CONFIG_ENTRY_ID] = config_entry.entry_id
        assert hass.services.has_service(DOMAIN, SERVICE_FETCH_CONNECTIONS)
        response = await hass.services.async_call(
            domain=DOMAIN,
            service=SERVICE_FETCH_CONNECTIONS,
            service_data=data,
            blocking=True,
            return_response=True,
        )
        await hass.async_block_till_done()
        assert response["connections"] is not None
        assert len(response["connections"]) == data.get(ATTR_LIMIT, CONNECTIONS_COUNT)


@pytest.mark.parametrize(
    ("limit", "config_data", "expected_result", "raise_error"),
    [
        (-1, MOCK_DATA_STEP_BASE, pytest.raises(vol_er.MultipleInvalid), None),
        (0, MOCK_DATA_STEP_BASE, pytest.raises(vol_er.MultipleInvalid), None),
        (
            CONNECTIONS_MAX + 1,
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
    limit,
    config_data,
    expected_result,
    raise_error,
) -> None:
    """Test service call with standard error."""

    unique_id = unique_id_from_config(config_data)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        title=f"Service test call with limit={limit} and error={raise_error}",
        unique_id=unique_id,
        entry_id=f"entry_{unique_id}",
    )

    with patch(
        "homeassistant.components.swiss_public_transport.OpendataTransport",
        return_value=AsyncMock(),
    ) as mock:
        mock().connections = json.loads(load_fixture("connections.json", DOMAIN))

        await setup_integration(hass, config_entry)

        assert hass.services.has_service(DOMAIN, SERVICE_FETCH_CONNECTIONS)
        mock().async_get_data.side_effect = raise_error
        with expected_result:
            await hass.services.async_call(
                domain=DOMAIN,
                service=SERVICE_FETCH_CONNECTIONS,
                service_data={
                    ATTR_CONFIG_ENTRY_ID: config_entry.entry_id,
                    ATTR_LIMIT: limit,
                },
                blocking=True,
                return_response=True,
            )


async def test_service_call_load_unload(
    hass: HomeAssistant,
) -> None:
    """Test service call with integration error."""

    unique_id = unique_id_from_config(MOCK_DATA_STEP_BASE)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA_STEP_BASE,
        title="Service test call for unloaded entry",
        unique_id=unique_id,
        entry_id=f"entry_{unique_id}",
    )

    bad_entry_id = "bad_entry_id"

    with patch(
        "homeassistant.components.swiss_public_transport.OpendataTransport",
        return_value=AsyncMock(),
    ) as mock:
        mock().connections = json.loads(load_fixture("connections.json", DOMAIN))

        await setup_integration(hass, config_entry)

        assert hass.services.has_service(DOMAIN, SERVICE_FETCH_CONNECTIONS)
        response = await hass.services.async_call(
            domain=DOMAIN,
            service=SERVICE_FETCH_CONNECTIONS,
            service_data={
                ATTR_CONFIG_ENTRY_ID: config_entry.entry_id,
            },
            blocking=True,
            return_response=True,
        )
        await hass.async_block_till_done()
        assert response["connections"] is not None

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(
            ServiceValidationError, match=f"{config_entry.title} is not loaded"
        ):
            await hass.services.async_call(
                domain=DOMAIN,
                service=SERVICE_FETCH_CONNECTIONS,
                service_data={
                    ATTR_CONFIG_ENTRY_ID: config_entry.entry_id,
                },
                blocking=True,
                return_response=True,
            )

        with pytest.raises(
            ServiceValidationError,
            match=f'Swiss public transport integration instance "{bad_entry_id}" not found',
        ):
            await hass.services.async_call(
                domain=DOMAIN,
                service=SERVICE_FETCH_CONNECTIONS,
                service_data={
                    ATTR_CONFIG_ENTRY_ID: bad_entry_id,
                },
                blocking=True,
                return_response=True,
            )
