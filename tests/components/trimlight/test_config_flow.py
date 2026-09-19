"""Tests for the Trimlight config flow."""

from dataclasses import replace
from unittest.mock import MagicMock

from aiotrimlight import (
    TrimlightCommandError,
    TrimlightConnectionError,
    TrimlightError,
    TrimlightHTTPError,
    TrimlightProtocolError,
)
import pytest

from homeassistant.components.trimlight.const import CONF_DID, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import DID, HOST, MAC, NAME

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_trimlight")


@pytest.mark.parametrize(
    ("properties", "name"),
    [
        pytest.param({"did": DID, "name": NAME}, NAME, id="txt-name"),
        pytest.param({"did": DID}, "Test-controller", id="service-name"),
    ],
)
async def test_zeroconf(
    hass: HomeAssistant,
    zeroconf_info: ZeroconfServiceInfo,
    properties: dict[str, str],
    name: str,
) -> None:
    """Test discovery confirmation and creation of a uniquely identified entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(zeroconf_info, properties=properties),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {"host": HOST, "name": name}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == name
    assert result["data"] == {CONF_HOST: HOST, CONF_DID: DID, CONF_MAC: MAC}
    assert result["result"].unique_id == DID


@pytest.mark.parametrize("host", [HOST, "192.0.2.11"], ids=["duplicate", "new-address"])
async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    zeroconf_info: ZeroconfServiceInfo,
    mock_trimlight: MagicMock,
    host: str,
) -> None:
    """Test rediscovery updates the existing entry instead of creating another."""
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_HOST: host}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=zeroconf_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == HOST
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    mock_trimlight.get_device_info.assert_not_awaited()


async def test_invalid_discovery(
    hass: HomeAssistant, zeroconf_info: ZeroconfServiceInfo
) -> None:
    """Test discovery without a valid identity is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(zeroconf_info, properties={}),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(
            TrimlightConnectionError("connection failed"),
            "cannot_connect",
            id="connection",
        ),
        pytest.param(TrimlightHTTPError(503), "cannot_connect", id="http"),
        pytest.param(
            TrimlightCommandError(201, "MCU timeout"), "invalid_response", id="command"
        ),
        pytest.param(
            TrimlightProtocolError("invalid response"),
            "invalid_response",
            id="protocol",
        ),
    ],
)
async def test_discovery_error_and_recovery(
    hass: HomeAssistant,
    mock_trimlight: MagicMock,
    zeroconf_info: ZeroconfServiceInfo,
    exception: TrimlightError,
    reason: str,
) -> None:
    """Test failed validation and successful configuration on later discovery."""
    mock_trimlight.get_device_info.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=zeroconf_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason

    mock_trimlight.get_device_info.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=zeroconf_info
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_HOST: HOST, CONF_DID: DID, CONF_MAC: MAC}
    assert result["result"].unique_id == DID


async def test_user(hass: HomeAssistant) -> None:
    """Test manual setup directs users to automatic discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
