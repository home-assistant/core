"""Test the Frontier Silicon config flow."""

from unittest.mock import AsyncMock, patch

from afsapi import ConnectionError, InvalidPinException, NotImplementedException
import pytest

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.frontier_silicon.const import (
    CONF_WEBFSAPI_URL,
    DEFAULT_PIN,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


MOCK_DISCOVERY = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_udn="uuid:3dcc7100-f76c-11dd-87af-00226124ca30",
    ssdp_st="mock_st",
    ssdp_location="http://1.1.1.1/device",
    upnp={"SPEAKER-NAME": "Speaker Name"},
)

INVALID_MOCK_DISCOVERY = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_udn="uuid:3dcc7100-f76c-11dd-87af-00226124ca30",
    ssdp_st="mock_st",
    ssdp_location=None,
    upnp={"SPEAKER-NAME": "Speaker Name"},
)


@pytest.mark.parametrize(
    ("radio_id_return_value", "radio_id_side_effect"),
    [("mock_radio_id", None), (None, NotImplementedException)],
)
async def test_form_default_pin(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    radio_id_return_value: str | None,
    radio_id_side_effect: Exception | None,
) -> None:
    """Test manual device add with default pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_radio_id",
        return_value=radio_id_return_value,
        side_effect=radio_id_side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Name of the device"
    assert result2["data"] == {
        CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi",
        CONF_PIN: "1234",
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("radio_id_return_value", "radio_id_side_effect"),
    [("mock_radio_id", None), (None, NotImplementedException)],
)
async def test_form_nondefault_pin(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    radio_id_return_value: str | None,
    radio_id_side_effect: Exception | None,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_friendly_name",
        side_effect=InvalidPinException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "device_config"
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_radio_id",
        return_value=radio_id_return_value,
        side_effect=radio_id_side_effect,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_PIN: "4321"},
        )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Name of the device"
    assert result3["data"] == {
        CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi",
        CONF_PIN: "4321",
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("friendly_name_error", "result_error"),
    [
        (ConnectionError, "cannot_connect"),
        (InvalidPinException, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
async def test_form_nondefault_pin_invalid(
    hass: HomeAssistant,
    friendly_name_error: Exception,
    result_error: str,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the proper errors when trying to validate an user-provided PIN."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_friendly_name",
        side_effect=InvalidPinException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "device_config"
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_friendly_name",
        side_effect=friendly_name_error,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_PIN: "4321"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result2["step_id"] == "device_config"
    assert result3["errors"] == {"base": result_error}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {CONF_PIN: "4321"},
    )
    await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Name of the device"
    assert result4["data"] == {
        CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi",
        CONF_PIN: "4321",
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("webfsapi_endpoint_error", "result_error"),
    [
        (ConnectionError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_invalid_device_url(
    hass: HomeAssistant,
    webfsapi_endpoint_error: Exception,
    result_error: str,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow when the user provides an invalid device IP/hostname."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_webfsapi_endpoint",
        side_effect=webfsapi_endpoint_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": result_error}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Name of the device"
    assert result3["data"] == {
        CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi",
        CONF_PIN: "1234",
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("radio_id_return_value", "radio_id_side_effect"),
    [("mock_radio_id", None), (None, NotImplementedException)],
)
async def test_ssdp(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
    radio_id_return_value: str | None,
    radio_id_side_effect: Exception | None,
) -> None:
    """Test a device being discovered."""
    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_radio_id",
        return_value=radio_id_return_value,
        side_effect=radio_id_side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=MOCK_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Name of the device"
    assert result2["data"] == {
        CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi",
        CONF_PIN: DEFAULT_PIN,
    }
    mock_setup_entry.assert_called_once()


async def test_ssdp_invalid_location(hass: HomeAssistant) -> None:
    """Test a device being discovered."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=INVALID_MOCK_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test an already known device being discovered."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("webfsapi_endpoint_error", "result_error"),
    [(ValueError, "unknown"), (ConnectionError, "cannot_connect")],
)
async def test_ssdp_fail(
    hass: HomeAssistant, webfsapi_endpoint_error: Exception, result_error: str
) -> None:
    """Test a device being discovered but failing to reply."""
    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_webfsapi_endpoint",
        side_effect=webfsapi_endpoint_error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=MOCK_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == result_error


async def test_ssdp_nondefault_pin(hass: HomeAssistant) -> None:
    """Test a device being discovered."""

    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_friendly_name",
        side_effect=InvalidPinException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=MOCK_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_reauth_flow(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test reauth flow."""
    config_entry.add_to_hass(hass)
    assert config_entry.data[CONF_PIN] == "1234"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": config_entry.unique_id,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_config"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "4242"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PIN] == "4242"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (ConnectionError, "cannot_connect"),
        (InvalidPinException, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
async def test_reauth_flow_friendly_name_error(
    hass: HomeAssistant,
    exception: Exception,
    reason: str,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with failures."""
    config_entry.add_to_hass(hass)
    assert config_entry.data[CONF_PIN] == "1234"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": config_entry.unique_id,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_config"

    with patch(
        "homeassistant.components.frontier_silicon.config_flow.AFSAPI.get_friendly_name",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "4321"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "device_config"
    assert result2["errors"] == {"base": reason}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "4242"},
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PIN] == "4242"
