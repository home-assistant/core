"""Test Radarr config flow."""
from unittest.mock import AsyncMock, patch

from aiopyarr import ArrException
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.radarr.const import DEFAULT_NAME, DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from . import (
    API_KEY,
    CONF_DATA,
    CONF_IMPORT_DATA,
    MOCK_REAUTH_INPUT,
    MOCK_USER_INPUT,
    URL,
    mock_connection,
    mock_connection_error,
    mock_connection_invalid_auth,
    patch_async_setup_entry,
    setup_integration,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


def _patch_setup():
    return patch("homeassistant.components.radarr.async_setup_entry")


@pytest.fixture(name="supervisor")
def mock_supervisor_fixture():
    """Mock Supervisor."""
    with patch(
        "homeassistant.components.radarr.config_flow.is_hassio", return_value=True
    ):
        yield


@pytest.fixture(name="addon")
def mock_addon_fixture():
    """Mock addon."""
    with patch(
        "homeassistant.components.radarr.config_flow.get_addons_info",
        return_value={"radarr": {"slug": "radarr_nas", "network": {"7878/tcp": 7887}}},
    ):
        yield


async def test_flow_import(hass: HomeAssistant):
    """Test import step."""
    with patch(
        "homeassistant.components.radarr.config_flow.RadarrClient.async_get_system_status",
        return_value=AsyncMock(),
    ), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONF_IMPORT_DATA,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["data"] == CONF_DATA | {
            CONF_URL: "http://192.168.1.189:7887/test"
        }
        assert result["data"][CONF_URL] == "http://192.168.1.189:7887/test"


async def test_flow_import_already_configured(hass: HomeAssistant):
    """Test import step already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.radarr.config_flow.RadarrClient.async_get_system_status",
        return_value=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONF_IMPORT_DATA,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["step_id"] == "manual"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on connection error."""
    mock_connection_error(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: "manual"},
        data=MOCK_USER_INPUT,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on invalid auth."""
    mock_connection_invalid_auth(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: "manual"}, data=MOCK_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_wrong_app(hass: HomeAssistant) -> None:
    """Test we show user form on wrong app."""
    with patch(
        "homeassistant.components.radarr.config_flow.RadarrClient.async_try_zeroconf",
        return_value="wrong_app",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: "manual"},
            data={CONF_URL: URL, CONF_VERIFY_SSL: False},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "wrong_app"}


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test we show user form on unknown error."""
    with patch(
        "homeassistant.components.radarr.config_flow.RadarrClient.async_get_system_status",
        side_effect=ArrException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: "manual"},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "unknown"}


async def test_on_supervisor(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, supervisor, addon
) -> None:
    """Test flow with supervisor addon."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "on_supervisor"

    with patch(
        "homeassistant.components.radarr.config_flow.RadarrClient.async_try_zeroconf",
        return_value=("v3", API_KEY, "/test"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"use_addon": True},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA | {
        CONF_URL: "http://homeassistant.local:7887/test"
    }


async def test_on_supervisor_internal_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, supervisor, addon
) -> None:
    """Test flow with supervisor addon with internal url preferred."""
    await async_process_ha_core_config(
        hass,
        {
            "internal_url": "http://test.local:8124",
            "external_url": "https://example.duckdns.org:8123",
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "on_supervisor"

    with patch(
        "homeassistant.components.radarr.config_flow.RadarrClient.async_try_zeroconf",
        return_value=("v3", API_KEY, "/test"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"use_addon": True},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA | {CONF_URL: "http://test.local:7887/test"}


async def test_on_supervisor_external_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, supervisor, addon
) -> None:
    """Test flow with supervisor addon with only external url configured."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.duckdns.org:8123"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "on_supervisor"

    with patch(
        "homeassistant.components.radarr.config_flow.RadarrClient.async_try_zeroconf",
        return_value=("v3", API_KEY, ""),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"use_addon": True},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA | {CONF_URL: "https://example.duckdns.org:7887"}


async def test_supervisor_manual(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, supervisor, addon
) -> None:
    """Test manual flow with supervisor addon."""
    mock_connection(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_addon": False},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.radarr.config_flow.RadarrClient.async_try_zeroconf",
        return_value=("v3", API_KEY, "/test"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA


async def test_full_reauth_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the manual reauth flow from start to finish."""
    entry = await setup_integration(hass, aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            CONF_SOURCE: SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_REAUTH_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"

    assert entry.data == CONF_DATA | {CONF_API_KEY: "test-api-key-reauth"}

    mock_setup_entry.assert_called_once()


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    mock_connection(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA
    assert result["data"][CONF_URL] == "http://192.168.1.189:7887/test"
