"""Test the DoorBird config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.doorbird.const import (
    CONF_EVENTS,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_MOTION_EVENT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "friend",
    CONF_PASSWORD: "password",
    CONF_NAME: "mydoorbird",
}


def _get_mock_doorbirdapi_return_values(ready=None, info=None):
    doorbirdapi_mock = MagicMock()
    type(doorbirdapi_mock).ready = AsyncMock(return_value=ready)
    type(doorbirdapi_mock).info = AsyncMock(return_value=info)
    type(doorbirdapi_mock).doorbell_state = AsyncMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=Mock(), history=Mock(), status=401
        )
    )
    return doorbirdapi_mock


def _get_mock_doorbirdapi_side_effects(ready=None, info=None):
    doorbirdapi_mock = MagicMock()
    type(doorbirdapi_mock).ready = AsyncMock(side_effect=ready)
    type(doorbirdapi_mock).info = AsyncMock(side_effect=info)

    return doorbirdapi_mock


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    doorbirdapi = _get_mock_doorbirdapi_return_values(
        ready=[True], info={"WIFI_MAC_ADDR": "macaddr"}
    )
    with (
        patch(
            "homeassistant.components.doorbird.config_flow.DoorBird",
            return_value=doorbirdapi,
        ),
        patch(
            "homeassistant.components.doorbird.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.doorbird.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.2.3.4"
    assert result2["data"] == {
        "host": "1.2.3.4",
        "name": "mydoorbird",
        "password": "password",
        "username": "friend",
    }
    assert result2["options"] == {
        CONF_EVENTS: [DEFAULT_DOORBELL_EVENT, DEFAULT_MOTION_EVENT]
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_zeroconf_wrong_oui(hass: HomeAssistant) -> None:
    """Test we abort when we get the wrong OUI via zeroconf."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.8"),
            ip_addresses=[ip_address("192.168.1.8")],
            hostname="mock_hostname",
            name="Doorstation - abc123._axis-video._tcp.local.",
            port=None,
            properties={"macaddress": "notdoorbirdoui"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_doorbird_device"


async def test_form_zeroconf_link_local_ignored(hass: HomeAssistant) -> None:
    """Test we abort when we get a link local address via zeroconf."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("169.254.103.61"),
            ip_addresses=[ip_address("169.254.103.61")],
            hostname="mock_hostname",
            name="Doorstation - abc123._axis-video._tcp.local.",
            port=None,
            properties={"macaddress": "1CCAE3DOORBIRD"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "link_local_address"


async def test_form_zeroconf_ipv4_address(hass: HomeAssistant) -> None:
    """Test we abort and update the ip address from zeroconf with an ipv4 address."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1CCAE3AAAAAA",
        data=VALID_CONFIG,
        options={CONF_EVENTS: ["event1", "event2", "event3"]},
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("4.4.4.4"),
            ip_addresses=[ip_address("4.4.4.4")],
            hostname="mock_hostname",
            name="Doorstation - abc123._axis-video._tcp.local.",
            port=None,
            properties={"macaddress": "1CCAE3AAAAAA"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "4.4.4.4"


async def test_form_zeroconf_non_ipv4_ignored(hass: HomeAssistant) -> None:
    """Test we abort when we get a non ipv4 address via zeroconf."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("fd00::b27c:63bb:cc85:4ea0"),
            ip_addresses=[ip_address("fd00::b27c:63bb:cc85:4ea0")],
            hostname="mock_hostname",
            name="Doorstation - abc123._axis-video._tcp.local.",
            port=None,
            properties={"macaddress": "1CCAE3DOORBIRD"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_ipv4_address"


async def test_form_zeroconf_correct_oui(hass: HomeAssistant) -> None:
    """Test we can setup from zeroconf with the correct OUI source."""
    doorbirdapi = _get_mock_doorbirdapi_return_values(
        ready=[True], info={"WIFI_MAC_ADDR": "macaddr"}
    )

    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("192.168.1.5"),
                ip_addresses=[ip_address("192.168.1.5")],
                hostname="mock_hostname",
                name="Doorstation - abc123._axis-video._tcp.local.",
                port=None,
                properties={"macaddress": "1CCAE3DOORBIRD"},
                type="mock_type",
            ),
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.doorbird.config_flow.DoorBird",
            return_value=doorbirdapi,
        ),
        patch("homeassistant.components.logbook.async_setup", return_value=True),
        patch(
            "homeassistant.components.doorbird.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.doorbird.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_CONFIG
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.2.3.4"
    assert result2["data"] == {
        "host": "1.2.3.4",
        "name": "mydoorbird",
        "password": "password",
        "username": "friend",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "doorbell_state_side_effect",
    [
        aiohttp.ClientResponseError(request_info=Mock(), history=Mock(), status=404),
        OSError,
        None,
    ],
)
async def test_form_zeroconf_correct_oui_wrong_device(
    hass: HomeAssistant, doorbell_state_side_effect
) -> None:
    """Test we can setup from zeroconf with the correct OUI source but not a doorstation."""
    doorbirdapi = _get_mock_doorbirdapi_return_values(
        ready=[True], info={"WIFI_MAC_ADDR": "macaddr"}
    )
    type(doorbirdapi).doorbell_state = AsyncMock(side_effect=doorbell_state_side_effect)

    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("192.168.1.5"),
                ip_addresses=[ip_address("192.168.1.5")],
                hostname="mock_hostname",
                name="Doorstation - abc123._axis-video._tcp.local.",
                port=None,
                properties={"macaddress": "1CCAE3DOORBIRD"},
                type="mock_type",
            ),
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_doorbird_device"


async def test_form_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    doorbirdapi = _get_mock_doorbirdapi_side_effects(ready=OSError)
    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle cannot invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_error = aiohttp.ClientResponseError(
        request_info=Mock(), history=Mock(), status=401
    )
    doorbirdapi = _get_mock_doorbirdapi_side_effects(ready=mock_error)
    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abcde12345",
        data=VALID_CONFIG,
        options={CONF_EVENTS: ["event1", "event2", "event3"]},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.doorbird.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_EVENTS: "eventa,   eventc,    eventq"}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert config_entry.options == {CONF_EVENTS: ["eventa", "eventc", "eventq"]}
