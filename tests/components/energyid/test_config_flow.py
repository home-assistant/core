"""Test the EnergyID config flow."""
from unittest.mock import AsyncMock, patch

from energyid_webhooks.metercatalog import MeterCatalog
import pytest

from homeassistant import config_entries
from homeassistant.components.energyid.config_flow import CannotConnect, InvalidUrl
from homeassistant.components.energyid.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"webhook_url": "invalid_url"}
