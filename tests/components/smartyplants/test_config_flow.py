"""Test the SmartyPlants config flow."""

from unittest.mock import AsyncMock

from pysmartyplants import SmartyPlantsAuthError, SmartyPlantsConnectionError
import pytest

from homeassistant.components.smartyplants.const import (
    CONF_WEBHOOK_SECRET,
    DEFAULT_HOST,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ACCOUNT_ID

from tests.common import MockConfigEntry

API_KEY = "sp_test_key_12345678"


@pytest.fixture
async def external_url(hass: HomeAssistant) -> None:
    """Give Home Assistant an address reachable from the internet.

    Without one the flow has no usable webhook URL to offer and skips
    straight to creating the entry.
    """
    await async_process_ha_core_config(hass, {"external_url": "https://example.test"})


USER_INPUT = {CONF_API_KEY: API_KEY}
ENTRY_DATA = {CONF_HOST: DEFAULT_HOST, CONF_API_KEY: API_KEY}


async def test_full_flow_with_webhook_secret(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    external_url: None,
) -> None:
    """The happy path stores credentials, a webhook id and the secret."""
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
    # The user needs the URL to paste into the SmartyPlants app.
    assert "webhook_url" in result["description_placeholders"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_WEBHOOK_SECRET: "s3cret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SmartyPlants"
    assert result["data"][CONF_API_KEY] == API_KEY
    assert result["data"][CONF_WEBHOOK_SECRET] == "s3cret"
    assert result["data"][CONF_WEBHOOK_ID]


async def test_flow_without_webhook_secret(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    external_url: None,
) -> None:
    """Skipping the secret is allowed and leaves the integration polling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_WEBHOOK_SECRET not in result["data"]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (SmartyPlantsAuthError, "invalid_auth"),
        (SmartyPlantsConnectionError, "cannot_connect"),
    ],
)
async def test_flow_errors_then_recovers(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    external_url: None,
    error: type[Exception],
    expected: str,
) -> None:
    """A failing check is reported and the user can correct it."""
    mock_client.async_verify.side_effect = error("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    mock_client.async_verify.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "webhook"


async def test_duplicate_account_aborts(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """The same host and key cannot be added twice."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_ID,
        data=ENTRY_DATA,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_rotated_key_is_not_a_duplicate_account(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Adding the same account with a rotated key aborts rather than duplicating."""
    MockConfigEntry(domain=DOMAIN, unique_id=ACCOUNT_ID, data=ENTRY_DATA).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "sp_rotated_key_87654321",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_the_flow_never_asks_for_a_server(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    external_url: None,
) -> None:
    """Everyone connects to the SmartyPlants service, so only a key is asked for."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert list(result["data_schema"].schema) == [CONF_API_KEY]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Still recorded on the entry, so an existing installation keeps working
    # and there is one place to look when debugging.
    assert result["data"][CONF_HOST] == DEFAULT_HOST


async def test_no_external_url_skips_the_webhook_step(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Without a reachable address there is no webhook URL worth offering.

    SmartyPlants calls the webhook from the internet, so showing a LAN-only
    address would give the user something that cannot work. The entry is
    created and readings arrive on the poll instead.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_WEBHOOK_SECRET not in result["data"]
