"""Tests for the Aprilaire config flow."""

from unittest.mock import AsyncMock, patch

from pyaprilaire.client import AprilaireClient
from pyaprilaire.const import FunctionalDomain
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aprilaire.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def client() -> AprilaireClient:
    """Return a mock client."""
    return AsyncMock(AprilaireClient)


async def test_config_flow_invalid_data(
    client: AprilaireClient, hass: HomeAssistant
) -> None:
    """Test that the flow shows an error with invalid data and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pyaprilaire.client.AprilaireClient", return_value=client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 7000,
            },
        )

    client.start_listen.assert_called_once()
    client.wait_for_response.assert_called_once_with(
        FunctionalDomain.IDENTIFICATION, 2, 30
    )
    client.stop_listen.assert_called_once()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_failed"}

    client.data = {"mac_address": "1:2:3:4:5:6"}

    with (
        patch("pyaprilaire.client.AprilaireClient", return_value=client),
        patch(
            "homeassistant.components.aprilaire.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 7000,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "1:2:3:4:5:6"


async def test_config_flow_data(client: AprilaireClient, hass: HomeAssistant) -> None:
    """Test the config flow with valid data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    client.data = {"mac_address": "1:2:3:4:5:6"}

    client.wait_for_response = AsyncMock(return_value={"mac_address": "1:2:3:4:5:6"})

    with (
        patch("pyaprilaire.client.AprilaireClient", return_value=client),
        patch(
            "homeassistant.components.aprilaire.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 7000,
            },
        )
        await hass.async_block_till_done()

    client.start_listen.assert_called_once()
    client.wait_for_response.assert_any_call(FunctionalDomain.CONTROL, 7, 30)
    client.wait_for_response.assert_any_call(FunctionalDomain.SENSORS, 2, 30)
    client.stop_listen.assert_called_once()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AprilAire"
    assert result["data"] == {
        "host": "localhost",
        "port": 7000,
    }
    assert result["result"].unique_id == "1:2:3:4:5:6"


async def test_config_flow_already_configured(
    client: AprilaireClient, hass: HomeAssistant
) -> None:
    """Test the config flow aborts when the device is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1:2:3:4:5:6",
        data={"host": "localhost", "port": 7000},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    client.data = {"mac_address": "1:2:3:4:5:6"}

    with patch("pyaprilaire.client.AprilaireClient", return_value=client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 7000,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
