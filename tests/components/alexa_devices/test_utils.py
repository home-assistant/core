"""Tests for Alexa Devices utils."""

from unittest.mock import AsyncMock

from aioamazondevices.exceptions import CannotConnect, CannotRetrieveData
import pytest

from homeassistant.components.alexa_devices.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry

ENTITY_ID = "switch.echo_test_do_not_disturb"


@pytest.mark.parametrize(
    ("side_effect", "key", "error"),
    [
        (CannotConnect, "cannot_connect_with_error", "CannotConnect()"),
        (CannotRetrieveData, "cannot_retrieve_data_with_error", "CannotRetrieveData()"),
    ],
)
async def test_alexa_api_call_exceptions(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    key: str,
    error: str,
) -> None:
    """Test alexa_api_call decorator for exceptions."""

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF

    mock_amazon_devices_client.set_do_not_disturb.side_effect = side_effect

    # Call API
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == key
    assert exc_info.value.translation_placeholders == {"error": error}
