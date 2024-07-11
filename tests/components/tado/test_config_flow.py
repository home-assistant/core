"""Test the Tado config flow."""

from http import HTTPStatus
from ipaddress import ip_address
from unittest.mock import MagicMock, patch

import PyTado
import pytest
import requests

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.tado.config_flow import NoHomes
from homeassistant.components.tado.const import (
    CONF_FALLBACK,
    CONST_OVERLAY_TADO_DEFAULT,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _get_mock_tado_api(getMe=None) -> MagicMock:
    mock_tado = MagicMock()
    if isinstance(getMe, Exception):
        type(mock_tado).getMe = MagicMock(side_effect=getMe)
    else:
        type(mock_tado).getMe = MagicMock(return_value=getMe)
    return mock_tado


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (KeyError, "invalid_auth"),
        (RuntimeError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test we handle Form Exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tado.config_flow.Tado",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Test a retry to recover, upon failure
    mock_tado_api = _get_mock_tado_api(getMe={"homes": [{"id": 1, "name": "myhome"}]})

    with (
        patch(
            "homeassistant.components.tado.config_flow.Tado",
            return_value=mock_tado_api,
        ),
        patch(
            "homeassistant.components.tado.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "myhome"
    assert result["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, data={"username": "test-username"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.tado.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_FALLBACK: CONST_OVERLAY_TADO_DEFAULT},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_FALLBACK: CONST_OVERLAY_TADO_DEFAULT}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test we can setup though the user path."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_tado_api = _get_mock_tado_api(getMe={"homes": [{"id": 1, "name": "myhome"}]})

    with (
        patch(
            "homeassistant.components.tado.config_flow.Tado",
            return_value=mock_tado_api,
        ),
        patch(
            "homeassistant.components.tado.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "myhome"
    assert result["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    response_mock = MagicMock()
    type(response_mock).status_code = HTTPStatus.UNAUTHORIZED
    mock_tado_api = _get_mock_tado_api(getMe=requests.HTTPError(response=response_mock))

    with patch(
        "homeassistant.components.tado.config_flow.Tado",
        return_value=mock_tado_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    response_mock = MagicMock()
    type(response_mock).status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_tado_api = _get_mock_tado_api(getMe=requests.HTTPError(response=response_mock))

    with patch(
        "homeassistant.components.tado.config_flow.Tado",
        return_value=mock_tado_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_homes(hass: HomeAssistant) -> None:
    """Test we handle no homes error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_tado_api = _get_mock_tado_api(getMe={"homes": []})

    with patch(
        "homeassistant.components.tado.config_flow.Tado",
        return_value=mock_tado_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_homes"}


async def test_form_homekit(hass: HomeAssistant) -> None:
    """Test that we abort from homekit if tado is already setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "AA:BB:CC:DD:EE:FF"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    flow = next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert flow["context"]["unique_id"] == "AA:BB:CC:DD:EE:FF"

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "AA:BB:CC:DD:EE:FF"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (PyTado.exceptions.TadoWrongCredentialsException, "invalid_auth"),
        (RuntimeError, "cannot_connect"),
        (NoHomes, "no_homes"),
        (ValueError, "unknown"),
    ],
)
async def test_reconfigure_flow(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test re-configuration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "test-username",
            "password": "test-password",
            "home_id": 1,
        },
        unique_id="unique_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.tado.config_flow.Tado",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_tado_api = _get_mock_tado_api(getMe={"homes": [{"id": 1, "name": "myhome"}]})
    with (
        patch(
            "homeassistant.components.tado.config_flow.Tado",
            return_value=mock_tado_api,
        ),
        patch(
            "homeassistant.components.tado.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry
    assert entry.title == "Mock Title"
    assert entry.data == {
        "username": "test-username",
        "password": "test-password",
        "home_id": 1,
    }
