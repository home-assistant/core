"""Define tests for the The Things Network init."""

# https://github.com/home-assistant/core/blob/dev/tests/components/daikin/test_init.py
# https://developers.home-assistant.io/docs/development_testing/
# https://developers.home-assistant.io/docs/core/entity/sensor

from unittest.mock import AsyncMock, patch

import pytest
from ttn_client import TTNAuthError, TTNSensorValue

from homeassistant.components.thethingsnetwork.const import (
    CONF_ACCESS_KEY,
    CONF_APP_ID,
    CONF_HOSTNAME,
    DOMAIN,
    TTN_API_HOSTNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

APPLICATION_ID = "test_app_id"


CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    unique_id=APPLICATION_ID,
    title=None,
    data={
        CONF_APP_ID: APPLICATION_ID,
        CONF_HOSTNAME: TTN_API_HOSTNAME,
        CONF_ACCESS_KEY: "dummy",
    },
)

DEVICE_ID = "my_device"
DEVICE_FIELD = "a_value"
DEVICE_FIELD_VALUE = 42
DATA = {
    DEVICE_ID: {
        "DEVICE_FIELD": TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            DEVICE_FIELD,
            DEVICE_FIELD_VALUE,
        )
    }
}


@pytest.fixture
def mock_TTNClient():
    """Mock TTNClient."""

    with patch(
        "homeassistant.components.thethingsnetwork.coordinator.TTNClient"
    ) as TTNClient:
        instance = TTNClient.return_value
        instance.fetch_data = AsyncMock(return_value=DATA)
        yield TTNClient


async def test_normal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_TTNClient,
) -> None:
    """Test a working configuratioms."""
    CONFIG_ENTRY.add_to_hass(hass)
    assert await hass.config_entries.async_setup(CONFIG_ENTRY.entry_id)

    await hass.async_block_till_done()

    # Check devices
    assert (
        device_registry.async_get_device(identifiers={(APPLICATION_ID, DEVICE_ID)}).name
        == DEVICE_ID
    )

    # Check entities
    assert entity_registry.async_get(f"sensor.{DEVICE_ID}_{DEVICE_FIELD}")

    # Test reaction to options update
    hass.config_entries.async_update_entry(
        CONFIG_ENTRY, data=CONFIG_ENTRY.data, options={"dummy": "new_value"}
    )


@pytest.mark.parametrize(("exceptionClass"), [TTNAuthError, Exception])
async def test_client_exceptions(
    hass: HomeAssistant, mock_TTNClient, exceptionClass
) -> None:
    """Test TTN Exceptions."""

    async def raise_TTNError():
        raise exceptionClass()

    mock_TTNClient.return_value.fetch_data = raise_TTNError
    CONFIG_ENTRY.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(CONFIG_ENTRY.entry_id)
