"""Test the Kostal Plenticore Solar Inverter config flow."""

from collections.abc import Generator
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from pykoplenti import ApiClient, AuthenticationException, SettingsData
import pytest

from homeassistant import config_entries
from homeassistant.components.kostal_plenticore.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_apiclient() -> ApiClient:
    """Return a mocked ApiClient instance."""
    apiclient = MagicMock(spec=ApiClient)
    apiclient.__aenter__.return_value = apiclient
    apiclient.__aexit__ = AsyncMock()

    return apiclient


@pytest.fixture
def mock_apiclient_class(mock_apiclient) -> Generator[type[ApiClient]]:
    """Return a mocked ApiClient class."""
    with patch(
        "homeassistant.components.kostal_plenticore.config_flow.ApiClient",
        autospec=True,
    ) as mock_api_class:
        mock_api_class.return_value = mock_apiclient
        yield mock_api_class


async def test_form_g1(
    hass: HomeAssistant,
    mock_apiclient_class: type[ApiClient],
    mock_apiclient: ApiClient,
) -> None:
    """Test the config flow for G1 models."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.kostal_plenticore.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        # mock of the context manager instance
        mock_apiclient.login = AsyncMock()
        mock_apiclient.get_settings = AsyncMock(
            return_value={
                "scb:network": [
                    SettingsData(
                        min="1",
                        max="63",
                        default=None,
                        access="readwrite",
                        unit=None,
                        id="Hostname",
                        type="string",
                    ),
                ]
            }
        )
        mock_apiclient.get_setting_values = AsyncMock(
            # G1 model has the entry id "Hostname"
            return_value={"scb:network": {"Hostname": "scb"}}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

        mock_apiclient_class.assert_called_once_with(ANY, "1.1.1.1")
        mock_apiclient.__aenter__.assert_called_once()
        mock_apiclient.__aexit__.assert_called_once()
        mock_apiclient.login.assert_called_once_with("test-password")
        mock_apiclient.get_settings.assert_called_once()
        mock_apiclient.get_setting_values.assert_called_once_with(
            "scb:network", "Hostname"
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "scb"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_g2(
    hass: HomeAssistant,
    mock_apiclient_class: type[ApiClient],
    mock_apiclient: ApiClient,
) -> None:
    """Test the config flow for G2 models."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.kostal_plenticore.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        # mock of the context manager instance
        mock_apiclient.login = AsyncMock()
        mock_apiclient.get_settings = AsyncMock(
            return_value={
                "scb:network": [
                    SettingsData(
                        min="1",
                        max="63",
                        default=None,
                        access="readwrite",
                        unit=None,
                        id="Network:Hostname",
                        type="string",
                    ),
                ]
            }
        )
        mock_apiclient.get_setting_values = AsyncMock(
            # G1 model has the entry id "Hostname"
            return_value={"scb:network": {"Network:Hostname": "scb"}}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

        mock_apiclient_class.assert_called_once_with(ANY, "1.1.1.1")
        mock_apiclient.__aenter__.assert_called_once()
        mock_apiclient.__aexit__.assert_called_once()
        mock_apiclient.login.assert_called_once_with("test-password")
        mock_apiclient.get_settings.assert_called_once()
        mock_apiclient.get_setting_values.assert_called_once_with(
            "scb:network", "Network:Hostname"
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "scb"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kostal_plenticore.config_flow.ApiClient"
    ) as mock_api_class:
        # mock of the context manager instance
        mock_api_ctx = MagicMock()
        mock_api_ctx.login = AsyncMock(
            side_effect=AuthenticationException(404, "invalid user"),
        )

        # mock of the return instance of ApiClient
        mock_api = MagicMock()
        mock_api.__aenter__.return_value = mock_api_ctx
        mock_api.__aexit__.return_value = None

        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kostal_plenticore.config_flow.ApiClient"
    ) as mock_api_class:
        # mock of the context manager instance
        mock_api_ctx = MagicMock()
        mock_api_ctx.login = AsyncMock(
            side_effect=TimeoutError(),
        )

        # mock of the return instance of ApiClient
        mock_api = MagicMock()
        mock_api.__aenter__.return_value = mock_api_ctx
        mock_api.__aexit__.return_value = None

        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"host": "cannot_connect"}


async def test_form_unexpected_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kostal_plenticore.config_flow.ApiClient"
    ) as mock_api_class:
        # mock of the context manager instance
        mock_api_ctx = MagicMock()
        mock_api_ctx.login = AsyncMock(
            side_effect=Exception(),
        )

        # mock of the return instance of ApiClient
        mock_api = MagicMock()
        mock_api.__aenter__.return_value = mock_api_ctx
        mock_api.__aexit__.return_value = None

        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test we handle already configured error."""
    MockConfigEntry(
        domain="kostal_plenticore",
        data={"host": "1.1.1.1", "password": "foobar"},
        unique_id="112233445566",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "password": "test-password",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
