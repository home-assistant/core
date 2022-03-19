"""Test NFAndroidTV config flow."""
from unittest.mock import MagicMock, patch

from aiohttp import ClientConnectorError
from notifications_android_tv.notifications import ConnectError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.nfandroidtv.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from . import (
    CONF_CONFIG_FLOW,
    CONF_DATA,
    CONF_DHCP_FLOW_ANDROID_TV,
    CONF_DHCP_FLOW_FIRE_TV,
    HOST,
    NAME,
    _create_mocked_tv,
    _patch_config_flow_tv,
    mock_response,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    with _patch_config_flow_tv(await _create_mocked_tv()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == NAME
        assert result["data"] == CONF_DATA


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
        unique_id=HOST,
    )

    entry.add_to_hass(hass)

    with _patch_config_flow_tv(await _create_mocked_tv()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with _patch_config_flow_tv(await _create_mocked_tv()) as tvmock:
        tvmock.side_effect = ConnectError
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_unknown_error(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with _patch_config_flow_tv(await _create_mocked_tv()) as tvmock:
        tvmock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}


async def test_flow_import(hass: HomeAssistant) -> None:
    """Test an import flow."""
    with _patch_config_flow_tv(await _create_mocked_tv()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=CONF_CONFIG_FLOW,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == CONF_DATA

    with _patch_config_flow_tv(await _create_mocked_tv()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=CONF_CONFIG_FLOW,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_import_missing_optional(hass: HomeAssistant) -> None:
    """Test an import flow with missing options."""
    with _patch_config_flow_tv(await _create_mocked_tv()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: HOST},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST, CONF_NAME: f"{DEFAULT_NAME} {HOST}"}


async def test_dhcp_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test discovery on already configured device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
        unique_id="1.1.1.1",
    )

    entry.add_to_hass(hass)
    assert entry.unique_id == "1.1.1.1"

    with _patch_config_flow_tv(await _create_mocked_tv()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_FIRE_TV,
        )
        assert entry.unique_id == "aa:bb:cc:dd:ee:ff"
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_dhcp_discovery_fire_tv(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we can process the Fire TV discovery from dhcp."""
    await mock_response(aioclient_mock)
    with _patch_config_flow_tv(await _create_mocked_tv()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_FIRE_TV,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_HOST: "1.1.1.1",
            CONF_NAME: "Fire TV 1.1.1.1",
        }
        assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_FIRE_TV,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_dhcp_discovery_fire_tv_not_valid(hass: HomeAssistant) -> None:
    """Test we can process the Fire TV discovery from dhcp with invalid device."""
    with _patch_config_flow_tv(await _create_mocked_tv()), patch(
        "aiohttp.ClientSession.get"
    ) as tvmock:
        error = MagicMock()
        error.errno = ""
        error.strerror = ""
        tvmock.side_effect = ClientConnectorError(error, error)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_FIRE_TV,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "not_valid_device"


async def test_dhcp_discovery_fire_tv_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test Fire TV discovery connect error."""
    await mock_response(aioclient_mock)
    with _patch_config_flow_tv(await _create_mocked_tv()) as tvmock:
        tvmock.side_effect = ConnectError
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_FIRE_TV,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "confirm_discovery_fire_tv"
        assert result["errors"] == {"base": "check_device"}


async def test_dhcp_discovery_android_tv(hass: HomeAssistant) -> None:
    """Test we can process the Android TV discovery from dhcp."""
    with _patch_config_flow_tv(await _create_mocked_tv()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_ANDROID_TV,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_HOST: "1.1.1.1",
            CONF_NAME: "Android TV 1.1.1.1",
        }
        assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_ANDROID_TV,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_dhcp_discovery_android_tv_cannot_connect(hass: HomeAssistant) -> None:
    """Test Android TV discovery connect error."""
    with _patch_config_flow_tv(await _create_mocked_tv()) as tvmock:
        tvmock.side_effect = ConnectError
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_ANDROID_TV,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "confirm_discovery_android_tv"
        assert result["errors"] == {"base": "check_device"}


async def test_dhcp_discovery_failed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test failed setup from dhcp."""
    await mock_response(aioclient_mock)
    with _patch_config_flow_tv(await _create_mocked_tv()) as tvmock:
        tvmock.side_effect = ConnectError
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_FIRE_TV,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    with _patch_config_flow_tv(await _create_mocked_tv()) as tvmock:
        tvmock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=CONF_DHCP_FLOW_FIRE_TV,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_in_progress"
