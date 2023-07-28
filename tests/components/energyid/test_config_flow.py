"""Test the EnergyID config flow."""
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.energyid.config_flow import (
    hass_entity_ids,
)
from homeassistant.components.energyid.const import (
    CONF_ENTITY_ID,
    CONF_WEBHOOK_URL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.components.energyid.common import (
    MOCK_CONFIG_ENTRY_DATA,
    MockHass,
    MockMeterCatalog,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    # Test with a single mocked Entity ID in the registry
    # and a mocked Meter Catalog
    with patch(
        "homeassistant.components.energyid.config_flow.hass_entity_ids",
        return_value=[MOCK_CONFIG_ENTRY_DATA[CONF_ENTITY_ID]],
    ), patch(
        "homeassistant.components.energyid.config_flow.WebhookClientAsync.get_meter_catalog",
        return_value=MockMeterCatalog(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}

        # Patch policy request to return True
        with patch(
            "homeassistant.components.energyid.config_flow.WebhookClientAsync.get_policy",
            return_value=True,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], MOCK_CONFIG_ENTRY_DATA
            )
            await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert (
            result2["title"]
            == f"Send {MOCK_CONFIG_ENTRY_DATA[CONF_ENTITY_ID]} to EnergyID"
        )
        assert result2["data"] == MOCK_CONFIG_ENTRY_DATA


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    (
        (
            aiohttp.ClientResponseError(
                aiohttp.RequestInfo(url="", method="GET", headers={}, real_url=""), None
            ),
            {"base": "cannot_connect"},
        ),
        (aiohttp.InvalidURL("test"), {CONF_WEBHOOK_URL: "invalid_url"}),
        (Exception, {"base": "unknown"}),
    ),
)
async def test_form__where_api_returns_error(
    hass: HomeAssistant, exception, expected_error
) -> None:
    """Test the behaviour of the config flow when the API returns an error."""

    # Test with a single mocked Entity ID in the registry
    # and a mocked Meter Catalog
    with patch(
        "homeassistant.components.energyid.config_flow.hass_entity_ids",
        return_value=[MOCK_CONFIG_ENTRY_DATA[CONF_ENTITY_ID]],
    ), patch(
        "homeassistant.components.energyid.config_flow.WebhookClientAsync.get_meter_catalog",
        return_value=MockMeterCatalog(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}

        # Patch policy request to raise the exception
        with patch(
            "homeassistant.components.energyid.config_flow.WebhookClientAsync.get_policy",
            side_effect=exception,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_ENTRY_DATA,
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == expected_error


async def test_hass_entity_ids() -> None:
    """Test hass entity ids."""
    ids = hass_entity_ids(MockHass())
    assert isinstance(ids, list)
    assert isinstance(ids[0], str)
