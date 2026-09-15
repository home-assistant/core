"""Test the SmartyPlants config flow."""

from unittest.mock import AsyncMock

from pysmartyplants import (
    SmartyPlantsAuthError,
    SmartyPlantsConnectionError,
    SmartyPlantsError,
    SmartyPlantsForbiddenError,
)
import pytest

from homeassistant.components.smartyplants.const import CONF_WEBHOOK_SECRET, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ACCOUNT_ID, API_KEY

from tests.common import MockConfigEntry

USER_INPUT = {CONF_API_KEY: API_KEY}


@pytest.fixture
async def external_url(hass: HomeAssistant) -> None:
    """Give Home Assistant an address reachable from the internet."""
    await async_process_ha_core_config(hass, {"external_url": "https://example.test"})


@pytest.mark.usefixtures("mock_smartyplants_client", "mock_setup_entry", "external_url")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the flow stores the key, a webhook id and the secret."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "webhook"
    assert "webhook_url" in result["description_placeholders"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_WEBHOOK_SECRET: "s3cret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SmartyPlants"
    assert result["result"].unique_id == ACCOUNT_ID
    assert result["data"][CONF_API_KEY] == API_KEY
    assert result["data"][CONF_WEBHOOK_SECRET] == "s3cret"
    assert result["data"][CONF_WEBHOOK_ID]


@pytest.mark.usefixtures("mock_smartyplants_client", "mock_setup_entry", "external_url")
async def test_flow_without_webhook_secret(hass: HomeAssistant) -> None:
    """Test the secret can be left empty to poll only."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_ID
    assert CONF_WEBHOOK_SECRET not in result["data"]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(SmartyPlantsAuthError("boom"), "invalid_auth", id="auth"),
        pytest.param(
            SmartyPlantsConnectionError("boom"), "cannot_connect", id="connection"
        ),
        pytest.param(SmartyPlantsForbiddenError("boom"), "forbidden", id="forbidden"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "external_url")
async def test_flow_errors_then_recovers(
    hass: HomeAssistant,
    mock_smartyplants_client: AsyncMock,
    error: SmartyPlantsError,
    expected: str,
) -> None:
    """Test a failed check is reported and the flow can still finish."""
    mock_smartyplants_client.async_verify.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    mock_smartyplants_client.async_verify.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_WEBHOOK_SECRET: "s3cret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_ID


@pytest.mark.parametrize(
    "api_key",
    [
        pytest.param(API_KEY, id="same_key"),
        pytest.param("sp_rotated_key_87654321", id="rotated_key"),
    ],
)
@pytest.mark.usefixtures("mock_smartyplants_client", "mock_setup_entry")
async def test_duplicate_account_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, api_key: str
) -> None:
    """Test the same account cannot be added twice, even with a rotated key."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: api_key}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_smartyplants_client", "mock_setup_entry")
async def test_no_external_url_skips_webhook_step(hass: HomeAssistant) -> None:
    """Test the webhook step is skipped when there is no address to offer."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_ID
    assert CONF_WEBHOOK_SECRET not in result["data"]
