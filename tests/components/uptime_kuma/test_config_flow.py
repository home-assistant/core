"""Test the Uptime Kuma config flow."""

from unittest.mock import AsyncMock

import pytest
from pythonkuma import UptimeKumaAuthenticationException, UptimeKumaConnectionException

from homeassistant.components.uptime_kuma.const import DOMAIN
from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_IGNORE, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ADDON_SERVICE_INFO

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org/",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "uptime.example.org"
    assert result["data"] == {
        CONF_URL: "https://uptime.example.org/",
        CONF_VERIFY_SSL: True,
        CONF_API_KEY: "apikey",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (UptimeKumaConnectionException, "cannot_connect"),
        (UptimeKumaAuthenticationException, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pythonkuma: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test we handle errors and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_pythonkuma.metrics.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org/",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_pythonkuma.metrics.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org/",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "uptime.example.org"
    assert result["data"] == {
        CONF_URL: "https://uptime.example.org/",
        CONF_VERIFY_SSL: True,
        CONF_API_KEY: "apikey",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org/",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_flow_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "newapikey"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_KEY] == "newapikey"

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (UptimeKumaConnectionException, "cannot_connect"),
        (UptimeKumaAuthenticationException, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_pythonkuma")
async def test_flow_reauth_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pythonkuma: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test reauth flow errors and recover."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_pythonkuma.metrics.side_effect = raise_error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "newapikey"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_pythonkuma.metrics.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "newapikey"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_KEY] == "newapikey"

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_flow_reconfigure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org:3001/",
            CONF_VERIFY_SSL: False,
            CONF_API_KEY: "newapikey",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {
        CONF_URL: "https://uptime.example.org:3001/",
        CONF_VERIFY_SSL: False,
        CONF_API_KEY: "newapikey",
    }

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (UptimeKumaConnectionException, "cannot_connect"),
        (UptimeKumaAuthenticationException, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_pythonkuma")
async def test_flow_reconfigure_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pythonkuma: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test reconfigure flow errors and recover."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pythonkuma.metrics.side_effect = raise_error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org:3001/",
            CONF_VERIFY_SSL: False,
            CONF_API_KEY: "newapikey",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_pythonkuma.metrics.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org:3001/",
            CONF_VERIFY_SSL: False,
            CONF_API_KEY: "newapikey",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {
        CONF_URL: "https://uptime.example.org:3001/",
        CONF_VERIFY_SSL: False,
        CONF_API_KEY: "newapikey",
    }

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_hassio_addon_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pythonkuma: AsyncMock,
) -> None:
    """Test config flow initiated by Supervisor."""
    mock_pythonkuma.metrics.side_effect = [UptimeKumaAuthenticationException, None]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_SERVICE_INFO,
        context={"source": SOURCE_HASSIO},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Uptime Kuma"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "apikey"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "a0d7b954_uptime-kuma"
    assert result["data"] == {
        CONF_URL: "http://localhost:3001/",
        CONF_VERIFY_SSL: True,
        CONF_API_KEY: "apikey",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_hassio_addon_discovery_confirm_only(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow initiated by Supervisor.

    Config flow will first try to configure without authentication and if it
    fails will show the form.
    """

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_SERVICE_INFO,
        context={"source": SOURCE_HASSIO},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Uptime Kuma"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "a0d7b954_uptime-kuma"
    assert result["data"] == {
        CONF_URL: "http://localhost:3001/",
        CONF_VERIFY_SSL: True,
        CONF_API_KEY: None,
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_hassio_addon_discovery_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test config flow initiated by Supervisor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://localhost:3001/",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_SERVICE_INFO,
        context={"source": SOURCE_HASSIO},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (UptimeKumaConnectionException, "cannot_connect"),
        (UptimeKumaAuthenticationException, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
async def test_hassio_addon_discovery_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pythonkuma: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test we handle errors and recover."""
    mock_pythonkuma.metrics.side_effect = UptimeKumaAuthenticationException
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_SERVICE_INFO,
        context={"source": SOURCE_HASSIO},
    )

    mock_pythonkuma.metrics.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "apikey"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_pythonkuma.metrics.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "apikey"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "a0d7b954_uptime-kuma"
    assert result["data"] == {
        CONF_URL: "http://localhost:3001/",
        CONF_VERIFY_SSL: True,
        CONF_API_KEY: "apikey",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_hassio_addon_discovery_ignored(
    hass: HomeAssistant,
) -> None:
    """Test we abort discovery flow if discovery was ignored."""

    MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IGNORE,
        data={},
        entry_id="123456789",
        unique_id="1234",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_SERVICE_INFO,
        context={"source": SOURCE_HASSIO},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_hassio_addon_discovery_update_info(
    hass: HomeAssistant,
) -> None:
    """Test we abort discovery flow if already configured and we update from discovery info."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="a0d7b954_uptime-kuma",
        data={
            CONF_URL: "http://localhost:80/",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
        entry_id="123456789",
        unique_id="1234",
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ADDON_SERVICE_INFO,
        context={"source": SOURCE_HASSIO},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_URL] == "http://localhost:3001/"
