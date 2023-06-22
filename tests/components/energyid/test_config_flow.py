"""Test the EnergyID config flow."""
from unittest.mock import AsyncMock, patch

from energyid_webhooks.metercatalog import MeterCatalog
from energyid_webhooks.webhookpolicy import WebhookPolicy
import pytest

from homeassistant import config_entries
from homeassistant.components.energyid.config_flow import (
    CannotConnect,
    InvalidInterval,
    InvalidUrl,
    hass_entity_ids,
    request_meter_catalog,
    validate_interval,
    validate_webhook,
)
from homeassistant.components.energyid.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.components.energyid.conftest import (
    MockEnergyIDConfigEntry,
    MockWebhookClientAsync,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.energyid.config_flow.hass_entity_ids",
        return_value=["test-entity-id"],
    ), patch(
        "homeassistant.components.energyid.config_flow.request_meter_catalog",
        return_value=MeterCatalog(
            meters=[{"metrics": {"test-metric": {"units": ["test-unit"]}}}]
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}

        with patch(
            "homeassistant.components.energyid.config_flow.validate_webhook",
            return_value=True,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "webhook_url": "https://hooks.energyid.eu/services/WebhookIn/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/xxxxxxxxxxxx",
                    "entity_id": "test-entity-id",
                    "metric": "test-metric",
                    "metric_kind": "cumulative",
                    "unit": "test-unit",
                },
            )
            await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Send test-entity-id to EnergyID"
        assert result2["data"] == {
            "webhook_url": "https://hooks.energyid.eu/services/WebhookIn/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/xxxxxxxxxxxx",
            "entity_id": "test-entity-id",
            "metric": "test-metric",
            "metric_kind": "cumulative",
            "unit": "test-unit",
        }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.energyid.config_flow.hass_entity_ids",
        return_value=["test-entity-id"],
    ), patch(
        "homeassistant.components.energyid.config_flow.request_meter_catalog",
        return_value=MeterCatalog(
            meters=[{"metrics": {"test-metric": {"units": ["test-unit"]}}}]
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.energyid.config_flow.validate_webhook",
            side_effect=CannotConnect,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "webhook_url": "https://hooks.energyid.eu/services/WebhookIn/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/xxxxxxxxxxxx",
                    "entity_id": "test-entity-id",
                    "metric": "test-metric",
                    "metric_kind": "cumulative",
                    "unit": "test-unit",
                },
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_url(hass: HomeAssistant) -> None:
    """Test we can handle invalid url error."""
    with patch(
        "homeassistant.components.energyid.config_flow.hass_entity_ids",
        return_value=["test-entity-id"],
    ), patch(
        "homeassistant.components.energyid.config_flow.request_meter_catalog",
        return_value=MeterCatalog(
            meters=[{"metrics": {"test-metric": {"units": ["test-unit"]}}}]
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.energyid.config_flow.validate_webhook",
            side_effect=InvalidUrl,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "webhook_url": "something invalid",
                    "entity_id": "test-entity-id",
                    "metric": "test-metric",
                    "metric_kind": "cumulative",
                    "unit": "test-unit",
                },
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"webhook_url": "invalid_url"}


async def test_form_unexpected_error(hass: HomeAssistant) -> None:
    """Test we can handle an unexpected error."""
    with patch(
        "homeassistant.components.energyid.config_flow.hass_entity_ids",
        return_value=["test-entity-id"],
    ), patch(
        "homeassistant.components.energyid.config_flow.request_meter_catalog",
        return_value=MeterCatalog(
            meters=[{"metrics": {"test-metric": {"units": ["test-unit"]}}}]
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.energyid.config_flow.validate_webhook",
            side_effect=Exception,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "webhook_url": "something invalid",
                    "entity_id": "test-entity-id",
                    "metric": "test-metric",
                    "metric_kind": "cumulative",
                    "unit": "test-unit",
                },
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


class MockHass:
    """Mock Home Assistant."""

    class MockStates:
        """Mock States."""

        def async_entity_ids(self) -> list:
            """Mock async_entity_ids."""
            return ["test-entity-id"]

    states = MockStates()


async def test_validate_webhook() -> None:
    """Test validate webhook."""
    client = MockWebhookClientAsync(
        webhook_url="https://hooks.energyid.eu/services/WebhookIn/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/xxxxxxxxxxxx",
        url_valid=True,
        can_connect=True,
    )
    assert await validate_webhook(client) is True

    client.url_valid = False
    with pytest.raises(InvalidUrl):
        await validate_webhook(client)

    client.url_valid = True
    client.can_connect = False
    with pytest.raises(CannotConnect):
        await validate_webhook(client)


async def test_validate_interval() -> None:
    """Test validate interval."""
    policy = WebhookPolicy(policy={"allowedInterval": "P1D"})
    interval = "P1D"
    assert await validate_interval(interval=interval, webhook_policy=policy) is True
    interval = "PT15M"
    with pytest.raises(InvalidInterval):
        await validate_interval(interval=interval, webhook_policy=policy)


async def test_request_meter_catalog() -> None:
    """Test meter catalog request."""
    client = MockWebhookClientAsync(webhook_url="https://test.url")
    catalog = await request_meter_catalog(client)
    assert isinstance(catalog, MeterCatalog)


async def test_hass_entity_ids() -> None:
    """Test hass entity ids."""
    ids = hass_entity_ids(MockHass())
    assert isinstance(ids, list)
    assert isinstance(ids[0], str)


async def test_options_form(hass: HomeAssistant) -> None:
    """Test we get the options form."""
    config_entry = MockEnergyIDConfigEntry()

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClientAsync",
        MockWebhookClientAsync,
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"data_interval": "P1D", "upload_interval": 300},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {"data_interval": "P1D", "upload_interval": 300}


async def test_options_form_invalid_interval(hass: HomeAssistant) -> None:
    """Test we get the options form, but with an invalid interval."""
    config_entry = MockEnergyIDConfigEntry()

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClientAsync",
        MockWebhookClientAsync,
    ):
        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"data_interval": "PT5M", "upload_interval": 300},
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"data_interval": "invalid_interval"}
