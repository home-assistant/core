"""Test the Kostal Plenticore Solar Inverter config flow."""

from collections.abc import Generator
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from pykoplenti import ApiClient, AuthenticationException, SettingsData
import pytest

from homeassistant import config_entries
from homeassistant.components.kostal_plenticore.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
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

        result = await hass.config_entries.flow.async_configure(
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
        mock_apiclient.login.assert_called_once_with("test-password", service_code=None)
        mock_apiclient.get_settings.assert_called_once()
        mock_apiclient.get_setting_values.assert_called_once_with(
            "scb:network", "Hostname"
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "scb"
    assert result["data"] == {
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

        result = await hass.config_entries.flow.async_configure(
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
        mock_apiclient.login.assert_called_once_with("test-password", service_code=None)
        mock_apiclient.get_settings.assert_called_once()
        mock_apiclient.get_setting_values.assert_called_once_with(
            "scb:network", "Network:Hostname"
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "scb"
    assert result["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_g2_with_service_code(
    hass: HomeAssistant,
    mock_apiclient_class: type[ApiClient],
    mock_apiclient: ApiClient,
) -> None:
    """Test the config flow for G2 models with a Service Code."""

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

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
                "service_code": "test-service-code",
            },
        )
        await hass.async_block_till_done()

        mock_apiclient_class.assert_called_once_with(ANY, "1.1.1.1")
        mock_apiclient.__aenter__.assert_called_once()
        mock_apiclient.__aexit__.assert_called_once()
        mock_apiclient.login.assert_called_once_with(
            "test-password", service_code="test-service-code"
        )
        mock_apiclient.get_settings.assert_called_once()
        mock_apiclient.get_setting_values.assert_called_once_with(
            "scb:network", "Network:Hostname"
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "scb"
    assert result["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
        "service_code": "test-service-code",
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

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"password": "invalid_auth"}


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

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "cannot_connect"}


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

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "password": "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_apiclient_class: type[ApiClient],
    mock_apiclient: ApiClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config flow for G1 models."""

    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

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

    result = await hass.config_entries.flow.async_configure(
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
    mock_apiclient.login.assert_called_once_with("test-password", service_code=None)
    mock_apiclient.get_settings.assert_called_once()
    mock_apiclient.get_setting_values.assert_called_once_with("scb:network", "Hostname")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # changed entry
    assert mock_config_entry.data[CONF_HOST] == "1.1.1.1"
    assert mock_config_entry.data[CONF_PASSWORD] == "test-password"


async def test_reconfigure_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle invalid auth while reconfiguring."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

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

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"password": "invalid_auth"}


async def test_reconfigure_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle cannot connect error."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

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

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "cannot_connect"}


async def test_reconfigure_unexpected_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle unexpected error."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

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

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_reconfigure_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle already configured error."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain="kostal_plenticore",
        data={CONF_HOST: "1.1.1.1", CONF_PASSWORD: "foobar"},
        unique_id="112233445566",
    ).add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
