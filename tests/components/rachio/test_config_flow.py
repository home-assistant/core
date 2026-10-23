"""Test the Rachio config flow."""

from ipaddress import ip_address
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.rachio.const import (
    CONF_CUSTOM_URL,
    CONF_MANUAL_RUN_MINS,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)

from tests.common import MockConfigEntry


def _mock_rachio_return_value(get=None, info=None):
    rachio_mock = MagicMock()
    person_mock = MagicMock()
    type(person_mock).get = MagicMock(return_value=get)
    type(person_mock).info = MagicMock(return_value=info)
    type(rachio_mock).person = person_mock
    return rachio_mock


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    rachio_mock = _mock_rachio_return_value(
        get=({"status": 200}, {"username": "myusername"}),
        info=({"status": 200}, {"id": "myid"}),
    )

    with (
        patch(
            "homeassistant.components.rachio.config_flow.Rachio",
            return_value=rachio_mock,
        ),
        patch(
            "homeassistant.components.rachio.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "api_key",
                CONF_CUSTOM_URL: "http://custom.url",
                CONF_MANUAL_RUN_MINS: 5,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "myusername"
    assert result2["data"] == {
        CONF_API_KEY: "api_key",
        CONF_CUSTOM_URL: "http://custom.url",
        CONF_MANUAL_RUN_MINS: 5,
    }
    assert result2["result"].unique_id == "api_key"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    rachio_mock = _mock_rachio_return_value(
        get=({"status": 200}, {"username": "myusername"}),
        info=({"status": 412}, {"error": "auth fail"}),
    )
    with patch(
        "homeassistant.components.rachio.config_flow.Rachio", return_value=rachio_mock
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "api_key"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    rachio_mock = _mock_rachio_return_value(
        get=({"status": 200}, {"username": "myusername"}),
        info=({"status": 200}, {"id": "myid"}),
    )
    with (
        patch(
            "homeassistant.components.rachio.config_flow.Rachio",
            return_value=rachio_mock,
        ),
        patch(
            "homeassistant.components.rachio.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "api_key"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    rachio_mock = _mock_rachio_return_value(
        get=({"status": 599}, {"username": "myusername"}),
        info=({"status": 200}, {"id": "myid"}),
    )
    with patch(
        "homeassistant.components.rachio.config_flow.Rachio", return_value=rachio_mock
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "api_key"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    rachio_mock = _mock_rachio_return_value(
        get=({"status": 200}, {"username": "myusername"}),
        info=({"status": 200}, {"id": "myid"}),
    )
    with (
        patch(
            "homeassistant.components.rachio.config_flow.Rachio",
            return_value=rachio_mock,
        ),
        patch(
            "homeassistant.components.rachio.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "api_key"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_form_homekit(hass: HomeAssistant) -> None:
    """Test that we abort from homekit if rachio is already setup."""

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

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "api_key"})
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
    assert result["reason"] == "already_configured"


async def test_form_homekit_ignored(hass: HomeAssistant) -> None:
    """Test that we abort from homekit if rachio is ignored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AA:BB:CC:DD:EE:FF",
        source=config_entries.SOURCE_IGNORE,
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
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test option flow."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "api_key"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # This should be improved at a later stage to increase test coverage
    hass.config_entries.options.async_abort(result["flow_id"])


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth updates the API key and unique ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "old_api_key", CONF_WEBHOOK_ID: "webhook_id"},
        unique_id="old_api_key",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    rachio_mock = _mock_rachio_return_value(
        get=({"status": 200}, {"username": "myusername"}),
        info=({"status": 200}, {"id": "myid"}),
    )
    with (
        patch(
            "homeassistant.components.rachio.config_flow.Rachio",
            return_value=rachio_mock,
        ) as mock_rachio,
        patch("homeassistant.components.rachio.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new_api_key"}
        )
        await hass.async_block_till_done()

    mock_rachio.assert_called_once_with("new_api_key")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {CONF_API_KEY: "new_api_key", CONF_WEBHOOK_ID: "webhook_id"}
    assert entry.unique_id == "new_api_key"


@pytest.mark.parametrize(
    ("rachio_patch", "error"),
    [
        pytest.param(
            {
                "return_value": _mock_rachio_return_value(
                    get=({"status": 200}, {"username": "myusername"}),
                    info=({"status": 403}, {"id": "myid"}),
                )
            },
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            {
                "return_value": _mock_rachio_return_value(
                    get=({"status": 500}, {"username": "myusername"}),
                    info=({"status": 200}, {"id": "myid"}),
                )
            },
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param({"side_effect": Exception}, "unknown", id="unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, rachio_patch: dict[str, Any], error: str
) -> None:
    """Test reauth handles errors and can recover."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "old_api_key"}, unique_id="old_api_key"
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch("homeassistant.components.rachio.config_flow.Rachio", **rachio_patch):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new_api_key"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    with (
        patch(
            "homeassistant.components.rachio.config_flow.Rachio",
            return_value=_mock_rachio_return_value(
                get=({"status": 200}, {"username": "myusername"}),
                info=({"status": 200}, {"id": "myid"}),
            ),
        ),
        patch("homeassistant.components.rachio.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new_api_key"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new_api_key"


async def test_reauth_api_key_used_by_other_entry(hass: HomeAssistant) -> None:
    """Test reauth aborts when the new API key belongs to another entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "old_api_key"}, unique_id="old_api_key"
    )
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "new_api_key"}, unique_id="new_api_key"
    ).add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.rachio.config_flow.Rachio",
        return_value=_mock_rachio_return_value(
            get=({"status": 200}, {"username": "myusername"}),
            info=({"status": 200}, {"id": "myid"}),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new_api_key"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_API_KEY] == "old_api_key"
    assert entry.unique_id == "old_api_key"
