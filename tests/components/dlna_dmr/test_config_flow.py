"""Test the DLNA config flow."""
import asyncio
from unittest.mock import Mock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.dlna_dmr.const import (
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DOMAIN as DLNA_DOMAIN,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_URL,
)
from homeassistant.core import HomeAssistant

from .conftest import (
    GOOD_DEVICE_LOCATION,
    GOOD_DEVICE_NAME,
    GOOD_DEVICE_TYPE,
    GOOD_DEVICE_UDN,
    NEW_DEVICE_LOCATION,
    UNCONTACTABLE_DEVICE_LOCATION,
    WRONG_ST_DEVICE_LOCATION,
    configure_device_requests_mock,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

WRONG_DEVICE_TYPE = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"

IMPORTED_DEVICE_NAME = "Imported DMR device"

MOCK_CONFIG_IMPORT_DATA = {
    CONF_PLATFORM: DLNA_DOMAIN,
    CONF_URL: GOOD_DEVICE_LOCATION,
}

MOCK_DISCOVERY = {
    ssdp.ATTR_SSDP_LOCATION: GOOD_DEVICE_LOCATION,
    ssdp.ATTR_UPNP_UDN: GOOD_DEVICE_UDN,
    ssdp.ATTR_UPNP_DEVICE_TYPE: GOOD_DEVICE_TYPE,
    ssdp.ATTR_UPNP_FRIENDLY_NAME: GOOD_DEVICE_NAME,
}


async def test_user_flow(hass: HomeAssistant, device_requests_mock) -> None:
    """Test user-init'd config flow with user entering a valid URL."""
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: GOOD_DEVICE_LOCATION}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == GOOD_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: GOOD_DEVICE_LOCATION,
        CONF_DEVICE_ID: GOOD_DEVICE_UDN,
        CONF_TYPE: GOOD_DEVICE_TYPE,
    }
    assert result["options"] == {CONF_POLL_AVAILABILITY: True}


async def test_user_flow_uncontactable(
    hass: HomeAssistant, device_requests_mock
) -> None:
    """Test user-init'd config flow with user entering an uncontactable URL."""
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: UNCONTACTABLE_DEVICE_LOCATION}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "could_not_connect"}
    assert result["step_id"] == "user"


async def test_user_flow_wrong_st(hass: HomeAssistant, device_requests_mock) -> None:
    """Test user-init'd config flow with user entering a URL for the wrong device."""
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: WRONG_ST_DEVICE_LOCATION}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "not_dmr"}
    assert result["step_id"] == "user"


async def test_import_flow_invalid(hass: HomeAssistant, device_requests_mock) -> None:
    """Test import flow of invalid YAML config."""
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_PLATFORM: DLNA_DOMAIN},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "incomplete_config"

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_PLATFORM: DLNA_DOMAIN, CONF_URL: UNCONTACTABLE_DEVICE_LOCATION},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "could_not_connect"

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_PLATFORM: DLNA_DOMAIN, CONF_URL: WRONG_ST_DEVICE_LOCATION},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "not_dmr"


async def test_import_flow_ssdp_discovered(
    hass: HomeAssistant, mock_ssdp_scanner: Mock
) -> None:
    """Test import of YAML config with a device also found via SSDP."""
    mock_ssdp_scanner.async_get_discovery_info_by_st.side_effect = [
        [MOCK_DISCOVERY],
        [],
        [],
    ]
    with patch(
        "homeassistant.components.dlna_dmr.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DLNA_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_IMPORT_DATA,
        )
        await hass.async_block_till_done()

    assert mock_ssdp_scanner.async_get_discovery_info_by_st.call_count >= 1
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == GOOD_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: GOOD_DEVICE_LOCATION,
        CONF_DEVICE_ID: GOOD_DEVICE_UDN,
        CONF_TYPE: GOOD_DEVICE_TYPE,
    }
    assert result["options"] == {
        CONF_LISTEN_PORT: None,
        CONF_CALLBACK_URL_OVERRIDE: None,
        CONF_POLL_AVAILABILITY: False,
    }

    # The config entry should not be duplicated when dlna_dmr is restarted
    mock_ssdp_scanner.async_get_discovery_info_by_st.side_effect = [
        [MOCK_DISCOVERY],
        [],
        [],
    ]
    with patch(
        "homeassistant.components.dlna_dmr.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DLNA_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_IMPORT_DATA,
        )
    assert not mock_setup_entry.called
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_direct_connect(
    hass: HomeAssistant, mock_ssdp_scanner: Mock, device_requests_mock
) -> None:
    """Test import of YAML config with a device *not found* via SSDP."""
    mock_ssdp_scanner.async_get_discovery_info_by_st.return_value = []

    with patch(
        "homeassistant.components.dlna_dmr.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DLNA_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_IMPORT_DATA,
        )
        await hass.async_block_till_done()

    assert mock_ssdp_scanner.async_get_discovery_info_by_st.call_count >= 1
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == GOOD_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: GOOD_DEVICE_LOCATION,
        CONF_DEVICE_ID: GOOD_DEVICE_UDN,
        CONF_TYPE: GOOD_DEVICE_TYPE,
    }
    assert result["options"] == {
        CONF_LISTEN_PORT: None,
        CONF_CALLBACK_URL_OVERRIDE: None,
        CONF_POLL_AVAILABILITY: True,
    }

    # The config entry should not be duplicated when dlna_dmr is restarted
    with patch(
        "homeassistant.components.dlna_dmr.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DLNA_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_IMPORT_DATA,
        )
    assert not mock_setup_entry.called
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_options(
    hass: HomeAssistant, mock_ssdp_scanner: Mock, device_requests_mock
) -> None:
    """Test import of YAML config with options set."""
    mock_ssdp_scanner.async_get_discovery_info_by_st.return_value = []

    with patch(
        "homeassistant.components.dlna_dmr.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DLNA_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_PLATFORM: DLNA_DOMAIN,
                CONF_URL: GOOD_DEVICE_LOCATION,
                CONF_NAME: IMPORTED_DEVICE_NAME,
                CONF_LISTEN_PORT: 2222,
                CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == IMPORTED_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: GOOD_DEVICE_LOCATION,
        CONF_DEVICE_ID: GOOD_DEVICE_UDN,
        CONF_TYPE: GOOD_DEVICE_TYPE,
    }
    assert result["options"] == {
        CONF_LISTEN_PORT: 2222,
        CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        CONF_POLL_AVAILABILITY: True,
    }


async def test_import_flow_deferred_ssdp(
    hass: HomeAssistant, mock_ssdp_scanner: Mock, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test YAML import of unavailable device later found via SSDP."""
    # Attempted import at hass start fails because device is unavailable
    mock_ssdp_scanner.async_get_discovery_info_by_st.side_effect = [
        [],
        [],
        [],
    ]
    aioclient_mock.get(GOOD_DEVICE_LOCATION, exc=asyncio.TimeoutError)
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_PLATFORM: DLNA_DOMAIN,
            CONF_URL: GOOD_DEVICE_LOCATION,
            CONF_NAME: IMPORTED_DEVICE_NAME,
            CONF_LISTEN_PORT: 2222,
            CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "could_not_connect"

    # Device becomes available then discovered via SSDP, import now occurs automatically
    mock_ssdp_scanner.async_get_discovery_info_by_st.side_effect = [
        [MOCK_DISCOVERY],
        [],
        [],
    ]
    aioclient_mock.clear_requests()
    configure_device_requests_mock(aioclient_mock)

    with patch(
        "homeassistant.components.dlna_dmr.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DLNA_DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=MOCK_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert hass.config_entries.flow.async_progress(include_uninitialized=True) == []

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == IMPORTED_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: GOOD_DEVICE_LOCATION,
        CONF_DEVICE_ID: GOOD_DEVICE_UDN,
        CONF_TYPE: GOOD_DEVICE_TYPE,
    }
    assert result["options"] == {
        CONF_LISTEN_PORT: 2222,
        CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        CONF_POLL_AVAILABILITY: False,
    }


async def test_import_flow_deferred_user(
    hass: HomeAssistant, mock_ssdp_scanner: Mock, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test YAML import of unavailable device later added by user."""
    # Attempted import at hass start fails because device is unavailable
    mock_ssdp_scanner.async_get_discovery_info_by_st.return_value = []
    aioclient_mock.get(GOOD_DEVICE_LOCATION, exc=asyncio.TimeoutError)
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_PLATFORM: DLNA_DOMAIN,
            CONF_URL: GOOD_DEVICE_LOCATION,
            CONF_NAME: IMPORTED_DEVICE_NAME,
            CONF_LISTEN_PORT: 2222,
            CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "could_not_connect"

    # Device becomes available then added by user, use all imported settings
    aioclient_mock.clear_requests()
    configure_device_requests_mock(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.dlna_dmr.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_URL: GOOD_DEVICE_LOCATION}
        )
        await hass.async_block_till_done()

    assert hass.config_entries.flow.async_progress(include_uninitialized=True) == []

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == IMPORTED_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: GOOD_DEVICE_LOCATION,
        CONF_DEVICE_ID: GOOD_DEVICE_UDN,
        CONF_TYPE: GOOD_DEVICE_TYPE,
    }
    assert result["options"] == {
        CONF_LISTEN_PORT: 2222,
        CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        CONF_POLL_AVAILABILITY: True,
    }


async def test_ssdp_flow_success(hass: HomeAssistant, device_requests_mock) -> None:
    """Test that SSDP discovery with an available device works."""
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == GOOD_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: GOOD_DEVICE_LOCATION,
        CONF_DEVICE_ID: GOOD_DEVICE_UDN,
        CONF_TYPE: GOOD_DEVICE_TYPE,
    }
    assert result["options"] == {}


async def test_ssdp_flow_unavailable(hass: HomeAssistant, aioclient_mock) -> None:
    """Test that SSDP discovery with an unavailable device gives an error message.

    This may occur if the device is turned on, discovered, then turned off
    before the user attempts to add it.
    """
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "confirm"

    aioclient_mock.get(GOOD_DEVICE_LOCATION, exc=asyncio.TimeoutError)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "could_not_connect"}
    assert result["step_id"] == "confirm"


async def test_ssdp_flow_bad_device(hass: HomeAssistant, aioclient_mock) -> None:
    """Test that SSDP discovery of a device with bad XML gives as error message.

    This may occur if the device is misbehaving.
    """
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "confirm"

    aioclient_mock.get(GOOD_DEVICE_LOCATION, text="Not valid XML")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "could_not_connect"}
    assert result["step_id"] == "confirm"


async def test_ssdp_flow_existing(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test that SSDP discovery of existing config entry updates the URL."""
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: NEW_DEVICE_LOCATION,
            ssdp.ATTR_UPNP_UDN: GOOD_DEVICE_UDN,
            ssdp.ATTR_UPNP_DEVICE_TYPE: GOOD_DEVICE_TYPE,
            ssdp.ATTR_UPNP_FRIENDLY_NAME: GOOD_DEVICE_NAME,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_mock.data[CONF_URL] == NEW_DEVICE_LOCATION


async def test_options_flow(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test config flow options."""
    result = await hass.config_entries.options.async_init(config_entry_mock.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {}

    # Invalid URL for callback (can't be validated automatically by voluptuous)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CALLBACK_URL_OVERRIDE: "Bad url",
            CONF_POLL_AVAILABILITY: False,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "invalid_url"}

    # Good data for all fields
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_LISTEN_PORT: 2222,
            CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
            CONF_POLL_AVAILABILITY: True,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_LISTEN_PORT: 2222,
        CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        CONF_POLL_AVAILABILITY: True,
    }
