"""Test the Tado config flow."""

from http import HTTPStatus
from ipaddress import ip_address
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import requests
import requests_mock

from homeassistant import config_entries
from homeassistant.components.tado import CONF_REFRESH_TOKEN
from homeassistant.components.tado.const import (
    CONF_FALLBACK,
    CONST_OVERLAY_TADO_DEFAULT,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)

from tests.common import MockConfigEntry, load_fixture


def _get_mock_tado_api(get_me=None) -> MagicMock:
    mock_tado = MagicMock()
    if isinstance(get_me, Exception):
        type(mock_tado).get_me = MagicMock(side_effect=get_me)
    else:
        type(mock_tado).get_me = MagicMock(return_value=get_me)
    return mock_tado


@pytest.mark.parametrize(
    ("exception"),
    [
        KeyError,
        RuntimeError,
        ValueError,
    ],
)
async def test_authentication_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we handle Form Exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tado.config_flow.Tado",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_prepare"

    mock_tado_api = _get_mock_tado_api(get_me={"homes": [{"id": 1, "name": "myhome"}]})

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
            {CONF_REFRESH_TOKEN: "refresh"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT

    # Test a retry to recover, upon failure
    with requests_mock.mock() as m:
        m.post(
            "https://login.tado.com/oauth2/device_authorize",
            text=load_fixture("tado/device_authorize.json"),
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth_prepare"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["step_id"] == "reauth_confirm"
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        m.post(
            "https://login.tado.com/oauth2/token", text=load_fixture("tado/token.json")
        )
        m.get("https://my.tado.com/api/v2/me", text=load_fixture("tado/me.json"))
        m.get(
            "https://my.tado.com/api/v2/homes/1/", text=load_fixture("tado/home.json")
        )

        freezer.tick(10)
        await hass.async_block_till_done()

        with (
            patch(
                "homeassistant.components.tado.async_setup_entry",
                return_value=True,
            ) as mock_setup_entry,
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
            await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "home name"
        assert result["data"] == {CONF_REFRESH_TOKEN: "refresh"}
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


async def test_create_entry(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test we can setup though the user path."""

    # I use a generic with to ensure all calls, including the polling checks are all in the same context
    with requests_mock.mock() as m:
        m.post(
            "https://login.tado.com/oauth2/device_authorize",
            text=load_fixture("tado/device_authorize.json"),
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth_prepare"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["step_id"] == "reauth_confirm"
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        m.post(
            "https://login.tado.com/oauth2/token", text=load_fixture("tado/token.json")
        )
        m.get("https://my.tado.com/api/v2/me", text=load_fixture("tado/me.json"))
        m.get(
            "https://my.tado.com/api/v2/homes/1/", text=load_fixture("tado/home.json")
        )

        freezer.tick(10)
        await hass.async_block_till_done()

        with (
            patch(
                "homeassistant.components.tado.async_setup_entry",
                return_value=True,
            ) as mock_setup_entry,
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
            await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "home name"
        assert result["data"] == {CONF_REFRESH_TOKEN: "refresh"}
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    response_mock = MagicMock()
    type(response_mock).status_code = HTTPStatus.UNAUTHORIZED
    mock_tado_api = _get_mock_tado_api(
        get_me=requests.HTTPError(response=response_mock)
    )

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
    mock_tado_api = _get_mock_tado_api(
        get_me=requests.HTTPError(response=response_mock)
    )

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

    mock_tado_api = _get_mock_tado_api(get_me={"homes": []})

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
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={ATTR_PROPERTIES_ID: "AA:BB:CC:DD:EE:FF"},
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
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={ATTR_PROPERTIES_ID: "AA:BB:CC:DD:EE:FF"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
