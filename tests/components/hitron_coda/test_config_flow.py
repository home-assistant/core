"""Test configuration and credential recovery for Hitron CODA."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hitron_coda.api import CannotConnect, InvalidAuth
from homeassistant.components.hitron_coda.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONFIG

pytestmark = pytest.mark.usefixtures("mock_client", "mock_setup_entry")


async def test_user_flow(hass: HomeAssistant) -> None:
    """Validate credentials before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG["host"]
    assert result["data"] == CONFIG


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        pytest.param(CannotConnect, "cannot_connect", id="connection"),
        pytest.param(InvalidAuth, "invalid_auth", id="credentials"),
        pytest.param(RuntimeError, "unknown", id="unexpected"),
    ],
)
async def test_user_error_and_recovery(
    hass: HomeAssistant,
    mock_client: MagicMock,
    error: type[Exception],
    expected_error: str,
) -> None:
    """Show errors without storing credentials, and allow a retry."""
    mock_client.get_devices.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert not hass.config_entries.async_entries(DOMAIN)

    mock_client.get_devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_IMPORT])
async def test_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    source: str,
) -> None:
    """Do not connect or create a second entry for the same router."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.get_devices.assert_not_called()


async def test_import(hass: HomeAssistant) -> None:
    """Import YAML credentials and polling interval."""
    data = {**CONFIG, "scan_interval": 30}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        pytest.param(CannotConnect, "cannot_connect", id="connection"),
        pytest.param(InvalidAuth, "invalid_auth", id="credentials"),
    ],
)
async def test_import_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    error: type[Exception],
    expected_error: str,
) -> None:
    """Abort imports that cannot validate the router."""
    mock_client.get_devices.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        pytest.param(CannotConnect, "cannot_connect", id="connection"),
        pytest.param(InvalidAuth, "invalid_auth", id="credentials"),
    ],
)
async def test_reauth_error_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: type[Exception],
    expected_error: str,
) -> None:
    """Keep existing credentials until replacement credentials are validated."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    credentials = {CONF_USERNAME: "new-admin", CONF_PASSWORD: "new-password"}
    mock_client.get_devices.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=credentials
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert mock_config_entry.data == CONFIG

    mock_client.get_devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=credentials
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {**CONFIG, **credentials}
