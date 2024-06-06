"""Test the Leslie's Pool Water Tests config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.leslies_pool.config_flow import (
    CannotConnect,
    InvalidAuth,
    InvalidURL,
)
from homeassistant.components.leslies_pool.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

WATER_TEST_URL = "https://lesliespool.com/on/demandware.store/Sites-lpm_site-Site/en_US/WaterTest-Landing?poolProfileId=5891278&poolName=Pool"


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.leslies_pool.api.LesliesPoolApi.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                "water_test_url": WATER_TEST_URL,
                CONF_SCAN_INTERVAL: 300,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Leslie's Pool"
    assert result["data"] == {
        "title": "Leslie's Pool",
        "username": "test-username",
        "password": "test-password",
        "pool_profile_id": "5891278",
        "pool_name": "Pool",
        "scan_interval": 300,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leslies_pool.api.LesliesPoolApi.authenticate",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                "water_test_url": WATER_TEST_URL,
                CONF_SCAN_INTERVAL: 300,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.leslies_pool.api.LesliesPoolApi.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                "water_test_url": WATER_TEST_URL,
                CONF_SCAN_INTERVAL: 300,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Leslie's Pool"
    assert result["data"] == {
        "title": "Leslie's Pool",
        "username": "test-username",
        "password": "test-password",
        "pool_profile_id": "5891278",
        "pool_name": "Pool",
        "scan_interval": 300,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leslies_pool.api.LesliesPoolApi.authenticate",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                "water_test_url": WATER_TEST_URL,
                CONF_SCAN_INTERVAL: 300,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.leslies_pool.api.LesliesPoolApi.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                "water_test_url": WATER_TEST_URL,
                CONF_SCAN_INTERVAL: 300,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Leslie's Pool"
    assert result["data"] == {
        "title": "Leslie's Pool",
        "username": "test-username",
        "password": "test-password",
        "pool_profile_id": "5891278",
        "pool_name": "Pool",
        "scan_interval": 300,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_url(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid URL error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leslies_pool.api.LesliesPoolApi.authenticate",
        side_effect=InvalidURL,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                "water_test_url": "invalid-url",
                CONF_SCAN_INTERVAL: 300,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}

    with patch(
        "homeassistant.components.leslies_pool.api.LesliesPoolApi.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                "water_test_url": WATER_TEST_URL,
                CONF_SCAN_INTERVAL: 300,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Leslie's Pool"
    assert result["data"] == {
        "title": "Leslie's Pool",
        "username": "test-username",
        "password": "test-password",
        "pool_profile_id": "5891278",
        "pool_name": "Pool",
        "scan_interval": 300,
    }
    assert len(mock_setup_entry.mock_calls) == 1
