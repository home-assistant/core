"""Tests for the Mealie config flow."""

from unittest.mock import AsyncMock

from aiomealie import About, MealieAuthenticationError, MealieConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.mealie.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from . import setup_integration

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "demo.mealie.io", CONF_API_TOKEN: "token"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mealie"
    assert result["data"] == {
        CONF_HOST: "demo.mealie.io",
        CONF_API_TOKEN: "token",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == "bf1c62fe-4941-4332-9886-e54e88dbdba0"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (MealieConnectionError, "cannot_connect"),
        (MealieAuthenticationError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    mock_mealie_client.get_user_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "demo.mealie.io", CONF_API_TOKEN: "token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_mealie_client.get_user_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "demo.mealie.io", CONF_API_TOKEN: "token"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_ingress_host(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test disallow ingress host."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "http://homeassistant/hassio/ingress/db21ed7f_mealie",
            CONF_API_TOKEN: "token",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "ingress_url"}

    mock_mealie_client.get_user_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://homeassistant:9001", CONF_API_TOKEN: "token"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("version"),
    [
        ("v1.0.0beta-5"),
        ("v1.0.0-RC2"),
        ("v0.1.0"),
    ],
)
async def test_flow_version_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    version,
) -> None:
    """Test flow version error."""
    mock_mealie_client.get_about.return_value = About(version=version)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "demo.mealie.io", CONF_API_TOKEN: "token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "mealie_version"}


async def test_duplicate(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "demo.mealie.io", CONF_API_TOKEN: "token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "token2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "token2"


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with wrong account."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_mealie_client.get_user_info.return_value.user_id = "wrong_user_id"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "token2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (MealieConnectionError, "cannot_connect"),
        (MealieAuthenticationError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_exceptions(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reauth flow errors."""
    await setup_integration(hass, mock_config_entry)
    mock_mealie_client.get_user_info.side_effect = exception

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_mealie_client.get_user_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "http://test:9090",
            CONF_API_TOKEN: "token2",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "token2"
    assert mock_config_entry.data[CONF_HOST] == "http://test:9090"
    assert mock_config_entry.data[CONF_VERIFY_SSL] is False


async def test_reconfigure_flow_wrong_account(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow with wrong account."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_mealie_client.get_user_info.return_value.user_id = "wrong_user_id"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://test:9090", CONF_API_TOKEN: "token2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (MealieConnectionError, "cannot_connect"),
        (MealieAuthenticationError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_reconfigure_flow_exceptions(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reconfigure flow errors."""
    await setup_integration(hass, mock_config_entry)
    mock_mealie_client.get_user_info.side_effect = exception

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://test:9090", CONF_API_TOKEN: "token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    mock_mealie_client.get_user_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://test:9090", CONF_API_TOKEN: "token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_hassio_success(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful Supervisor flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={"addon": "Mealie", "host": "http://test", "port": 9090},
            name="mealie",
            slug="mealie",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "hassio_confirm"
    assert result.get("description_placeholders") == {"addon": "Mealie"}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "token"}
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Mealie"
    assert result2["data"] == {
        CONF_HOST: "http://test:9090",
        CONF_API_TOKEN: "token",
        CONF_VERIFY_SSL: True,
    }
    assert result2["result"].unique_id == "bf1c62fe-4941-4332-9886-e54e88dbdba0"


async def test_hassio_already_configured(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN, data={"host": "mock-adguard", "port": "3000"}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "Mealie",
                "host": "mock-mealie",
                "port": "9090",
            },
            name="Mealie",
            slug="mealie",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_hassio_ignored(hass: HomeAssistant) -> None:
    """Test we supervisor discovered instance can be ignored."""
    MockConfigEntry(domain=DOMAIN, source=config_entries.SOURCE_IGNORE).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "Mealie",
                "host": "mock-mealie",
                "port": "9090",
            },
            name="Mealie",
            slug="mealie",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# async def test_hassio_connection_error(
#     hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
# ) -> None:
#     """Test we show Hass.io confirm form on AdGuard Home connection error."""
#     aioclient_mock.get(
#         "http://mock-adguard:3000/control/status", exc=aiohttp.ClientError
#     )

#     result = await hass.config_entries.flow.async_init(
#         DOMAIN,
#         data=HassioServiceInfo(
#             config={
#                 "addon": "AdGuard Home Addon",
#                 "host": "mock-adguard",
#                 "port": 3000,
#             },
#             name="AdGuard Home Addon",
#             slug="adguard",
#             uuid="1234",
#         ),
#         context={"source": config_entries.SOURCE_HASSIO},
#     )

#     result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

#     assert result
#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "hassio_confirm"
#     assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (MealieConnectionError, "cannot_connect"),
        (MealieAuthenticationError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_hassio_connection_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    mock_mealie_client.get_user_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={"addon": "Mealie", "host": "http://test", "port": 9090},
            name="mealie",
            slug="mealie",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "hassio_confirm"
    assert result.get("description_placeholders") == {"addon": "Mealie"}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "token"}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}

    mock_mealie_client.get_user_info.side_effect = None
