import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from frisquet_connect.config_flow import FrisquetConnectFlow
from utils import unstub_all


@pytest.mark.asyncio
async def test_async_config_flow_step_authentication(
    mock_hass: HomeAssistant, mock_entry: ConfigEntry
):
    config_flow = FrisquetConnectFlow()

    user_input = None
    await config_flow.async_step_user(user_input)

    user_input = None
    await config_flow.async_step_user(user_input)

    unstub_all()


@pytest.mark.asyncio
async def test_async_config_flow_step_site(
    mock_hass: HomeAssistant, mock_entry: ConfigEntry
):
    config_flow = FrisquetConnectFlow()

    user_input = None
    await config_flow.async_step_user(user_input)

    user_input = {"email": "firstname.lastname@domain.com", "password": "p@ssw0rd"}
    await config_flow.async_step_user(user_input)

    unstub_all()


@pytest.mark.asyncio
async def test_async_config_flow_all_step(
    mock_hass: HomeAssistant, mock_entry: ConfigEntry
):
    config_flow = FrisquetConnectFlow()

    user_input = None
    await config_flow.async_step_user(user_input)

    user_input = {
        "email": "firstname.lastname@domain.com",
        "password": "p@ssw0rd",
        "sites": [{"site_id": "12345678901234", "name": "Somewhere"}],
    }
    await config_flow.async_step_user(user_input)

    unstub_all()
