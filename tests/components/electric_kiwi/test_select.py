"""The tests for Electric Kiwi select."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from electrickiwi_api.exceptions import ApiException, AuthException
from electrickiwi_api.model import Hop
import pytest

from homeassistant.components.electric_kiwi.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration

from tests.common import MockConfigEntry, load_json_value_fixture

ENTITY_ID = "select.hour_of_free_power"
OPTION = "12:00 AM - 1:00 AM"


@pytest.mark.usefixtures("ek_auth")
async def test_select_option(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    electrickiwi_api: AsyncMock,
) -> None:
    """Test selecting a new hour of free power."""
    await init_integration(hass, config_entry)
    hop_data = load_json_value_fixture("get_hop.json", DOMAIN)
    hop_data["data"]["start"] = {"interval": "1", "start_time": "12:00 AM"}
    hop_data["data"]["end"] = {"interval": "2", "end_time": "1:00 AM"}
    electrickiwi_api.post_hop.return_value = Hop.from_dict(hop_data)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: OPTION},
        blocking=True,
    )

    electrickiwi_api.post_hop.assert_awaited_once_with(1)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == OPTION


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ApiException("API error"), id="api_error"),
        pytest.param(ClientError("Connection error"), id="client_error"),
        pytest.param(TimeoutError, id="timeout"),
    ],
)
@pytest.mark.usefixtures("ek_auth")
async def test_select_option_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    electrickiwi_api: AsyncMock,
    exception: Exception,
) -> None:
    """Test errors when selecting an hour of free power."""
    await init_integration(hass, config_entry)
    electrickiwi_api.post_hop.side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: OPTION},
            blocking=True,
        )

    assert exc_info.value.translation_key == "set_hop_failed"
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("ek_auth")
async def test_select_option_auth_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    electrickiwi_api: AsyncMock,
) -> None:
    """Test an auth error when selecting an hour of free power starts reauth."""
    await init_integration(hass, config_entry)
    electrickiwi_api.post_hop.side_effect = AuthException("Auth error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: OPTION},
            blocking=True,
        )

    assert exc_info.value.translation_key == "auth_failed"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
