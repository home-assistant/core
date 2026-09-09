"""Test the AirNow config flow."""

from typing import Any
from unittest.mock import AsyncMock

from pyairnow.errors import AirNowError, EmptyResponseError, InvalidKeyError
import pytest

from homeassistant import config_entries
from homeassistant.components.airnow.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_airnow")
async def test_form(
    hass: HomeAssistant, config: dict[str, Any], options: dict[str, Any]
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["description_placeholders"] == {
        "api_key_url": "https://docs.airnowapi.org/account/request/"
    }

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == config
    assert result2["options"] == options


@pytest.mark.parametrize("mock_api_get", [AsyncMock(side_effect=InvalidKeyError)])
@pytest.mark.usefixtures("setup_airnow")
async def test_form_invalid_auth(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize("data", [{}])
@pytest.mark.usefixtures("setup_airnow")
async def test_form_invalid_location(
    hass: HomeAssistant, config: dict[str, Any]
) -> None:
    """Test we handle invalid location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_location"}


@pytest.mark.parametrize("mock_api_get", [AsyncMock(side_effect=AirNowError)])
@pytest.mark.usefixtures("setup_airnow")
async def test_form_cannot_connect(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize("mock_api_get", [AsyncMock(side_effect=EmptyResponseError)])
@pytest.mark.usefixtures("setup_airnow")
async def test_form_empty_result(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test we handle empty response error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_location"}


@pytest.mark.parametrize("mock_api_get", [AsyncMock(side_effect=RuntimeError)])
@pytest.mark.usefixtures("setup_airnow")
async def test_form_unexpected(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test we handle an unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("config_entry")
async def test_entry_already_exists(
    hass: HomeAssistant, config: dict[str, Any]
) -> None:
    """Test that the form aborts if the Lat/Lng is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.usefixtures("setup_airnow")
@pytest.mark.parametrize(
    ("version", "entry_data", "entry_options"),
    [
        pytest.param(
            1,
            {
                CONF_API_KEY: "1234",
                CONF_LATITUDE: 33.6,
                CONF_LONGITUDE: -118.1,
                CONF_RADIUS: 25,
            },
            {},
            id="v1_radius_in_data",
        ),
        pytest.param(
            2,
            {
                CONF_API_KEY: "1234",
                CONF_LATITUDE: 33.6,
                CONF_LONGITUDE: -118.1,
            },
            {CONF_RADIUS: 10},
            id="v2_radius_in_options",
        ),
    ],
)
async def test_config_migration(
    hass: HomeAssistant,
    version: int,
    entry_data: dict[str, Any],
    entry_options: dict[str, Any],
) -> None:
    """Test that migration to Version 3 removes the radius option."""
    config_entry = MockConfigEntry(
        version=version,
        domain=DOMAIN,
        title="AirNow",
        data=entry_data,
        source=config_entries.SOURCE_USER,
        options=entry_options,
        unique_id="1234",
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 3
    assert CONF_RADIUS not in config_entry.data
    assert CONF_RADIUS not in config_entry.options
