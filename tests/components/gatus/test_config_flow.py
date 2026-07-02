"""Test the Gatus config flow."""

from unittest.mock import AsyncMock, patch

from gatus_api.client import GatusClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.gatus.config_flow import CannotConnect
from homeassistant.components.gatus.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form, validate the client, and create a successful entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
        AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gatus"
    assert result["data"] == {
        CONF_URL: "http://gatus.local:8080",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_url(hass: HomeAssistant) -> None:
    """Test handling of a malformed or relative URL without a scheme."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "gatus.local"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (GatusClientError("Cannot connect"), "cannot_connect"),
        (Exception("Unexpected backend explosion"), "unknown"),
    ],
)
async def test_form_failures_and_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test handling validation failures and ensuring the flow can completely recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    with patch(
        "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
        AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test that duplicate configurations for the same base URL abort early."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus.local:8080"},
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.local:8080"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_success(hass: HomeAssistant) -> None:
    """Test a pristine successful reconfiguration step updating an existing URL."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://old-gatus.local:8080"},
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "homeassistant.components.gatus.config_flow.GatusClient.get_endpoints_statuses",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.gatus.async_setup_entry",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://new-gatus.local:8080"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_URL] == "http://new-gatus.local:8080"
    assert len(mock_setup.mock_calls) == 1


async def test_reconfigure_invalid_url(hass: HomeAssistant) -> None:
    """Test that reconfiguration validates a relative or completely broken URL layout."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://old-gatus.local:8080"},
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "broken-url-no-scheme"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}


async def test_reconfigure_already_configured(hass: HomeAssistant) -> None:
    """Test that reconfiguring to a URL already managed by another entry aborts cleanly."""
    target_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus-one.local:8080"},
    )
    target_entry.add_to_hass(hass)

    collision_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus-two.local:8080"},
    )
    collision_entry.add_to_hass(hass)

    result = await target_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus-two.local:8080"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (CannotConnect, "cannot_connect"),
        (Exception("Reconfigure crash test"), "unknown"),
    ],
)
async def test_reconfigure_failures(
    hass: HomeAssistant, side_effect: Exception, error_key: str
) -> None:
    """Test validation handlers during the reconfiguration phase."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://old-gatus.local:8080"},
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.gatus.config_flow.validate_input",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://new-gatus.local:8080"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}
