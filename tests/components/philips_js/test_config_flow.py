"""Test the Philips TV config flow."""

from ipaddress import ip_address
import logging
from typing import Any
from unittest.mock import ANY, MagicMock

from haphilipsjs import ConnectionFailure, PairingFailure
import pytest

from homeassistant import config_entries
from homeassistant.components.philips_js.const import (
    CONF_ALLOW_NOTIFY,
    CONF_MENU_NODES,
    DOMAIN,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import (
    MOCK_CONFIG,
    MOCK_CONFIG_PAIRED,
    MOCK_HOSTNAME,
    MOCK_MENU_DATA,
    MOCK_MENU_STORAGE_KEY,
    MOCK_NAME,
    MOCK_PASSWORD,
    MOCK_SERIAL_NO,
    MOCK_SYSTEM,
    MOCK_SYSTEM_UNPAIRED,
    MOCK_USERINPUT,
    MOCK_USERNAME,
)

from tests.common import MockConfigEntry

MOCK_MENU_OPTIONS = [
    {"value": "2", "label": "Toggle"},
]


def _get_schema(result: ConfigFlowResult) -> dict[str, tuple[Any, Any]]:
    """Return the form schema keyed by field name."""
    return {
        key.schema: (key, value) for key, value in result["data_schema"].schema.items()
    }


@pytest.fixture
async def mock_tv_pairable(mock_tv):
    """Return a mock tv that is pariable."""
    mock_tv.system = MOCK_SYSTEM_UNPAIRED
    mock_tv.pairing_type = "digest_auth_pairing"
    mock_tv.api_version = 6
    mock_tv.api_version_detected = 6
    mock_tv.secured_transport = True
    mock_tv.name = MOCK_NAME

    mock_tv.pairRequest.return_value = {}
    mock_tv.pairGrant.return_value = MOCK_USERNAME, MOCK_PASSWORD
    return mock_tv


async def test_form(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USERINPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Philips TV (1234567890)"
    assert result2["data"] == MOCK_CONFIG
    assert result2["result"].unique_id == MOCK_SERIAL_NO
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth(
    hass: HomeAssistant, mock_setup_entry, mock_config_entry: MockConfigEntry, mock_tv
) -> None:
    """Test we get the form."""

    mock_tv.system = MOCK_SYSTEM | {"model": "changed"}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert len(mock_setup_entry.mock_calls) == 1

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USERINPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_config_entry.data == MOCK_CONFIG | {"system": mock_tv.system}
    assert len(mock_setup_entry.mock_calls) == 2


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect(hass: HomeAssistant, mock_tv: MagicMock) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_tv.system = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USERINPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_tv.system = MOCK_SYSTEM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USERINPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_pairing(hass: HomeAssistant, mock_tv_pairable, mock_setup_entry) -> None:
    """Test we get the form."""
    mock_tv = mock_tv_pairable

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USERINPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_tv.setTransport.assert_called_with(True, ANY)
    mock_tv.pairRequest.assert_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": "1234"}
    )

    assert result == {
        "context": {
            "source": "user",
            "unique_id": "ABCDEFGHIJKLF",
            "title_placeholders": {
                "name": "Philips TV",
            },
        },
        "flow_id": ANY,
        "type": "create_entry",
        "description": None,
        "description_placeholders": None,
        "handler": "philips_js",
        "result": ANY,
        "title": "55PUS7181/12 (ABCDEFGHIJKLF)",
        "data": MOCK_CONFIG_PAIRED,
        "version": 1,
        "options": {},
        "minor_version": 1,
        "subentries": (),
    }

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_pair_request_failed(hass: HomeAssistant, mock_tv_pairable) -> None:
    """Test we get the form."""
    mock_tv = mock_tv_pairable
    mock_tv.pairRequest.side_effect = PairingFailure({})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USERINPUT,
    )

    assert result == {
        "flow_id": ANY,
        "description_placeholders": {"error_id": None},
        "handler": "philips_js",
        "reason": "pairing_failure",
        "type": "abort",
    }


async def test_pair_grant_failed(hass: HomeAssistant, mock_tv_pairable) -> None:
    """Test we get the form."""
    mock_tv = mock_tv_pairable

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USERINPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_tv.setTransport.assert_called_with(True, ANY)
    mock_tv.pairRequest.assert_called()

    # Test with invalid pin
    mock_tv.pairGrant.side_effect = PairingFailure({"error_id": "INVALID_PIN"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": "1234"}
    )

    assert result["type"] is FlowResultType.FORM
    # pylint: disable-next=home-assistant-tests-config-flow-error-recovery
    assert result["errors"] == {"pin": "invalid_pin"}

    # Test with unexpected failure
    mock_tv.pairGrant.side_effect = PairingFailure({})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": "1234"}
    )

    assert result == {
        "flow_id": ANY,
        "description_placeholders": {"error_id": None},
        "handler": "philips_js",
        "reason": "pairing_failure",
        "type": "abort",
    }


async def test_options_flow(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test config flow options."""
    caplog.set_level(logging.DEBUG)
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    assert "Ignoring menu node 10 and its children without name" in caplog.text

    result = await hass.config_entries.options.async_init(
        mock_menu_config_entry.entry_id
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    schema = _get_schema(result)
    # Unknown node is not offered, so it is dropped from the default
    assert schema[CONF_ALLOW_NOTIFY][0].default() is True
    assert schema[CONF_MENU_NODES][0].default() == ["2"]
    assert schema[CONF_MENU_NODES][1].config["options"] == MOCK_MENU_OPTIONS

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ALLOW_NOTIFY: False, CONF_MENU_NODES: ["2"]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_menu_config_entry.options == {
        CONF_ALLOW_NOTIFY: False,
        CONF_MENU_NODES: [2],
    }


async def test_options_flow_cached_menu(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_menu_config_entry: MockConfigEntry,
) -> None:
    """Test options flow uses the stored menu, also when the entry is not loaded."""
    hass_storage[MOCK_MENU_STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": MOCK_MENU_STORAGE_KEY,
        "data": MOCK_MENU_DATA,
    }

    result = await hass.config_entries.options.async_init(
        mock_menu_config_entry.entry_id
    )

    assert result["type"] is FlowResultType.FORM
    schema = _get_schema(result)
    assert schema[CONF_MENU_NODES][0].default() == ["2"]
    assert schema[CONF_MENU_NODES][1].config["options"] == MOCK_MENU_OPTIONS


async def test_options_flow_menu_not_supported(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow on a TV without menu settings support."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    schema = _get_schema(result)
    assert schema[CONF_MENU_NODES][0].default() == []
    assert schema[CONF_MENU_NODES][1].config["options"] == []

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ALLOW_NOTIFY: True, CONF_MENU_NODES: []},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_ALLOW_NOTIFY: True,
        CONF_MENU_NODES: [],
    }


@pytest.mark.parametrize(
    "tv_config",
    [
        pytest.param({"update.return_value": False}, id="tv-off"),
        pytest.param({"settings": None}, id="no-settings"),
        pytest.param({"settings": {"node": {}}}, id="no-root-node"),
        pytest.param(
            {
                "getStringsCached.side_effect": None,
                "getStringsCached.return_value": None,
            },
            id="no-strings",
        ),
        pytest.param(
            {"getMenuItemsSettingsCurrentValue.side_effect": ConnectionFailure("")},
            id="connection-failure",
        ),
    ],
)
async def test_options_flow_menu_not_available(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    tv_config: dict[str, Any],
) -> None:
    """Test options flow aborts when the menu has never been read."""
    mock_tv.configure_mock(**tv_config)

    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_menu_config_entry.entry_id
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "menu_not_available"


@pytest.mark.parametrize(
    ("secured_transport", "discovery_type"),
    [(True, "_philipstv_s_rpc._tcp.local."), (False, "_philipstv_rpc._tcp.local.")],
)
async def test_zeroconf_discovery(
    hass: HomeAssistant, mock_tv_pairable, secured_transport, discovery_type
) -> None:
    """Test we can setup from zeroconf discovery."""

    mock_tv_pairable.secured_transport = secured_transport
    mock_tv_pairable.api_version_detected = 6
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname=MOCK_HOSTNAME,
            name=MOCK_NAME,
            port=None,
            properties={},
            type=discovery_type,
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_tv_pairable.setTransport.assert_called_with(secured_transport, 6)
    mock_tv_pairable.pairRequest.assert_called()


async def test_zeroconf_probe_failed(
    hass: HomeAssistant,
    mock_tv_pairable,
) -> None:
    """Test we can setup from zeroconf discovery."""

    mock_tv_pairable.system = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname=MOCK_HOSTNAME,
            name=MOCK_NAME,
            port=None,
            properties={},
            type="_philipstv_s_rpc._tcp.local.",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failure"
