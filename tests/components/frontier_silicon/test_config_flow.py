"""Test the Frontier Silicon config flow."""
from unittest.mock import patch

from afsapi import ConnectionError, InvalidPinException

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.frontier_silicon.const import (
    CONF_WEBFSAPI_URL,
    DEFAULT_PIN,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

VALID_DEVICE_URL_PATCH = patch(
    "afsapi.AFSAPI.get_webfsapi_endpoint",
    return_value="http://1.1.1.1:80/webfsapi",
)

INVALID_DEVICE_URL_PATCH = patch(
    "afsapi.AFSAPI.get_webfsapi_endpoint",
    side_effect=ConnectionError,
)

UNEXPECTED_ERROR_GET_WEBFSAPI_ENDPOINT_PATCH = patch(
    "afsapi.AFSAPI.get_webfsapi_endpoint",
    side_effect=ValueError,
)

VALID_DEVICE_CONFIG_PATCH = patch(
    "afsapi.AFSAPI.get_friendly_name",
    return_value="Name of the device",
)

INVALID_PIN_PATCH = patch(
    "afsapi.AFSAPI.get_friendly_name",
    side_effect=InvalidPinException,
)


async def test_import(hass: HomeAssistant) -> None:
    """Test import."""

    with VALID_DEVICE_URL_PATCH:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_PIN: "1234",
                CONF_NAME: "Test name",
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY

    with INVALID_DEVICE_URL_PATCH:

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_PIN: "1234",
                CONF_NAME: "Test name",
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"

    with UNEXPECTED_ERROR_GET_WEBFSAPI_ENDPOINT_PATCH:

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_PIN: "1234",
                CONF_NAME: "Test name",
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "unknown"

    with VALID_DEVICE_URL_PATCH, patch(
        "afsapi.AFSAPI.get_radio_id",
        side_effect=ConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_PIN: "1234",
                CONF_NAME: "Test name",
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"

    with VALID_DEVICE_URL_PATCH, patch(
        "afsapi.AFSAPI.get_radio_id",
        side_effect=InvalidPinException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_PIN: "1234",
                CONF_NAME: "Test name",
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "invalid_auth"

    with VALID_DEVICE_URL_PATCH, patch(
        "afsapi.AFSAPI.get_radio_id",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_PIN: "1234",
                CONF_NAME: "Test name",
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "unknown"


async def test_import_already_exists(hass: HomeAssistant, config_entry) -> None:
    """Test import of device which already exists."""
    config_entry.add_to_hass(hass)

    with VALID_DEVICE_URL_PATCH:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_PIN: "1234",
                CONF_NAME: "Test name",
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_form_default_pin(hass: HomeAssistant) -> None:
    """Test manual device add with default pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with VALID_DEVICE_URL_PATCH, VALID_DEVICE_CONFIG_PATCH, patch(
        "homeassistant.components.frontier_silicon.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Name of the device"
    assert result2["data"] == {
        "webfsapi_url": "http://1.1.1.1:80/webfsapi",
        "pin": "1234",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_nondefault_pin(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with VALID_DEVICE_URL_PATCH, INVALID_PIN_PATCH:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with VALID_DEVICE_CONFIG_PATCH, patch(
        "homeassistant.components.frontier_silicon.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "4321"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Name of the device"
    assert result3["data"] == {
        "webfsapi_url": "http://1.1.1.1:80/webfsapi",
        "pin": "4321",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_nondefault_pin_invalid(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with VALID_DEVICE_URL_PATCH, INVALID_PIN_PATCH:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with INVALID_PIN_PATCH:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "4321"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_auth"}

    with patch(
        "afsapi.AFSAPI.get_friendly_name",
        side_effect=ConnectionError,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "4321"},
        )

    assert result4["type"] == FlowResultType.FORM
    assert result4["errors"] == {"base": "cannot_connect"}

    with patch(
        "afsapi.AFSAPI.get_friendly_name",
        side_effect=ValueError,
    ):
        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "4321"},
        )

    assert result5["type"] == FlowResultType.FORM
    assert result5["errors"] == {"base": "unknown"}


async def test_invalid_device_url(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with INVALID_DEVICE_URL_PATCH:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_device_url_unexpected_error(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with UNEXPECTED_ERROR_GET_WEBFSAPI_ENDPOINT_PATCH:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_ssdp(hass):
    """Test a device being discovered."""

    with VALID_DEVICE_CONFIG_PATCH, VALID_DEVICE_URL_PATCH:

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_udn="mock_udn",
                ssdp_st="mock_st",
                ssdp_location="http://1.1.1.1/device",
                upnp={"SPEAKER-NAME": "Speaker Name"},
            ),
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Name of the device"
    assert result2["data"] == {
        CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi",
        CONF_PIN: DEFAULT_PIN,
    }


async def test_ssdp_nondefault_pin(hass):
    """Test a device being discovered."""

    with VALID_DEVICE_URL_PATCH, INVALID_PIN_PATCH:

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_udn="mock_udn",
                ssdp_st="mock_st",
                ssdp_location="http://1.1.1.1/device",
                upnp={"SPEAKER-NAME": "Speaker Name"},
            ),
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "device_config"

    with patch(
        "afsapi.AFSAPI.get_friendly_name",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "4321"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "afsapi.AFSAPI.get_friendly_name",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "4321"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with VALID_DEVICE_CONFIG_PATCH, patch(
        "homeassistant.components.frontier_silicon.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "4321"},
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Name of the device"
    assert result2["data"] == {
        CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi",
        CONF_PIN: "4321",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_fail(hass):
    """Test a device being discovered but failing to reply."""
    with UNEXPECTED_ERROR_GET_WEBFSAPI_ENDPOINT_PATCH:

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_udn="mock_udn",
                ssdp_st="mock_st",
                ssdp_location="http://1.1.1.1/device",
                upnp={"SPEAKER-NAME": "Speaker Name"},
            ),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"

    with INVALID_DEVICE_URL_PATCH:

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_udn="mock_udn",
                ssdp_st="mock_st",
                ssdp_location="http://1.1.1.1/device",
                upnp={"SPEAKER-NAME": "Speaker Name"},
            ),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
