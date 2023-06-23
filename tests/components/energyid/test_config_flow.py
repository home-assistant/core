"""Test the EnergyID config flow."""
from unittest.mock import patch

import aiohttp
from energyid_webhooks.webhookpolicy import WebhookPolicy
import pytest

from homeassistant import config_entries
from homeassistant.components.energyid.config_flow import (
    InvalidInterval,
    hass_entity_ids,
    validate_interval,
)
from homeassistant.components.energyid.const import (
    CONF_DATA_INTERVAL,
    CONF_ENTITY_ID,
    CONF_UPLOAD_INTERVAL,
    CONF_WEBHOOK_URL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.components.energyid.common import (
    MOCK_CONFIG_ENTRY_DATA,
    MOCK_CONFIG_OPTIONS,
    MockEnergyIDConfigEntry,
    MockHass,
    MockMeterCatalog,
    MockWebhookPolicy,
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

        # Patch validate_webhook to return True
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


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""

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

        # Patch policy request to raise ClientResponseError
        with patch(
            "homeassistant.components.energyid.config_flow.WebhookClientAsync.get_policy",
            side_effect=aiohttp.ClientResponseError(
                aiohttp.RequestInfo(
                    url=MOCK_CONFIG_ENTRY_DATA[CONF_WEBHOOK_URL],
                    method="GET",
                    headers={},
                    real_url=MOCK_CONFIG_ENTRY_DATA[CONF_WEBHOOK_URL],
                ),
                None,
                status=404,
            ),
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_ENTRY_DATA,
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_url(hass: HomeAssistant) -> None:
    """Test we can handle invalid url error."""

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

        # Patch policy request to raise InvalidUrl
        with patch(
            "homeassistant.components.energyid.config_flow.WebhookClientAsync.get_policy",
            side_effect=aiohttp.InvalidURL(
                url=MOCK_CONFIG_ENTRY_DATA[CONF_WEBHOOK_URL]
            ),
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_ENTRY_DATA,
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_WEBHOOK_URL: "invalid_url"}


async def test_form_unexpected_error(hass: HomeAssistant) -> None:
    """Test we can handle an unexpected error."""

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

        # Patch policy request to raise Exception
        with patch(
            "homeassistant.components.energyid.config_flow.WebhookClientAsync.get_policy",
            side_effect=Exception,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_ENTRY_DATA,
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_validate_interval() -> None:
    """Test validate interval."""
    policy = WebhookPolicy(policy={"allowedInterval": "P1D"})
    interval = "P1D"
    assert await validate_interval(interval=interval, webhook_policy=policy) is True
    interval = "PT15M"
    with pytest.raises(InvalidInterval):
        await validate_interval(interval=interval, webhook_policy=policy)


async def test_hass_entity_ids() -> None:
    """Test hass entity ids."""
    ids = hass_entity_ids(MockHass())
    assert isinstance(ids, list)
    assert isinstance(ids[0], str)


async def test_options_form(hass: HomeAssistant) -> None:
    """Test we get the options form."""
    config_entry = MockEnergyIDConfigEntry()

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClientAsync.policy",
        MockWebhookPolicy.async_init(),
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            MOCK_CONFIG_OPTIONS,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == MOCK_CONFIG_OPTIONS


async def test_options_form_invalid_interval(hass: HomeAssistant) -> None:
    """Test we get the options form, but with an invalid interval."""
    config_entry = MockEnergyIDConfigEntry()

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClientAsync.policy",
        MockWebhookPolicy.async_init(),
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_DATA_INTERVAL: "PT5M", CONF_UPLOAD_INTERVAL: 300},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_DATA_INTERVAL: "invalid_interval"}
