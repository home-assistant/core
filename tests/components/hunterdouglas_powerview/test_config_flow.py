"""Test the Logitech Harmony Hub config flow."""
import asyncio
from ipaddress import ip_address
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

ZEROCONF_HOST = "1.2.3.4"
HOMEKIT_DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address(ZEROCONF_HOST),
    ip_addresses=[ip_address(ZEROCONF_HOST)],
    hostname="mock_hostname",
    name="Hunter Douglas Powerview Hub._hap._tcp.local.",
    port=None,
    properties={zeroconf.ATTR_PROPERTIES_ID: "AA::BB::CC::DD::EE::FF"},
    type="mock_type",
)

ZEROCONF_DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address(ZEROCONF_HOST),
    ip_addresses=[ip_address(ZEROCONF_HOST)],
    hostname="mock_hostname",
    name="Hunter Douglas Powerview Hub._powerview._tcp.local.",
    port=None,
    properties={},
    type="mock_type",
)

DHCP_DISCOVERY_INFO = dhcp.DhcpServiceInfo(
    hostname="Hunter Douglas Powerview Hub",
    ip="1.2.3.4",
    macaddress="AA:BB:CC:DD:EE:FF",
)

DISCOVERY_DATA = [
    (
        config_entries.SOURCE_HOMEKIT,
        HOMEKIT_DISCOVERY_INFO,
    ),
    (
        config_entries.SOURCE_DHCP,
        DHCP_DISCOVERY_INFO,
    ),
    (config_entries.SOURCE_ZEROCONF, ZEROCONF_DISCOVERY_INFO),
]


def _get_mock_powerview_userdata(userdata=None, get_resources=None):
    mock_powerview_userdata = MagicMock()
    if not userdata:
        userdata = json.loads(load_fixture("hunterdouglas_powerview/userdata.json"))
    if get_resources:
        mock_powerview_userdata.get_resources = AsyncMock(side_effect=get_resources)
    else:
        mock_powerview_userdata.get_resources = AsyncMock(return_value=userdata)
    return mock_powerview_userdata


def _get_mock_powerview_legacy_userdata(userdata=None, get_resources=None):
    mock_powerview_userdata_legacy = MagicMock()
    if not userdata:
        userdata = json.loads(load_fixture("hunterdouglas_powerview/userdata_v1.json"))
    if get_resources:
        mock_powerview_userdata_legacy.get_resources = AsyncMock(
            side_effect=get_resources
        )
    else:
        mock_powerview_userdata_legacy.get_resources = AsyncMock(return_value=userdata)
    return mock_powerview_userdata_legacy


def _get_mock_powerview_fwversion(fwversion=None, get_resources=None):
    mock_powerview_fwversion = MagicMock()
    if not fwversion:
        fwversion = json.loads(load_fixture("hunterdouglas_powerview/fwversion.json"))
    if get_resources:
        mock_powerview_fwversion.get_resources = AsyncMock(side_effect=get_resources)
    else:
        mock_powerview_fwversion.get_resources = AsyncMock(return_value=fwversion)
    return mock_powerview_fwversion


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_powerview_userdata = _get_mock_powerview_userdata()
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "AlexanderHD"
    assert result2["data"] == {
        "host": "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result3["type"] == "form"
    assert result3["errors"] == {}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {"host": "1.2.3.4"},
    )
    assert result4["type"] == "abort"


async def test_user_form_legacy(hass: HomeAssistant) -> None:
    """Test we get the user form with a legacy device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_powerview_userdata = _get_mock_powerview_legacy_userdata()
    mock_powerview_fwversion = _get_mock_powerview_fwversion()
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.ApiEntryPoint",
        return_value=mock_powerview_fwversion,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "PowerView Hub Gen 1"
    assert result2["data"] == {
        "host": "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result3["type"] == "form"
    assert result3["errors"] == {}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {"host": "1.2.3.4"},
    )
    assert result4["type"] == "abort"


@pytest.mark.parametrize(("source", "discovery_info"), DISCOVERY_DATA)
async def test_form_homekit_and_dhcp_cannot_connect(
    hass: HomeAssistant, source, discovery_info
) -> None:
    """Test we get the form with homekit and dhcp source."""

    ignored_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, source=config_entries.SOURCE_IGNORE
    )
    ignored_config_entry.add_to_hass(hass)

    mock_powerview_userdata = _get_mock_powerview_userdata(
        get_resources=asyncio.TimeoutError
    )
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=discovery_info,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(("source", "discovery_info"), DISCOVERY_DATA)
async def test_form_homekit_and_dhcp(
    hass: HomeAssistant, source, discovery_info
) -> None:
    """Test we get the form with homekit and dhcp source."""

    ignored_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, source=config_entries.SOURCE_IGNORE
    )
    ignored_config_entry.add_to_hass(hass)

    mock_powerview_userdata = _get_mock_powerview_userdata()
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=discovery_info,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] is None
    assert result["description_placeholders"] == {
        "host": "1.2.3.4",
        "name": "Hunter Douglas Powerview Hub",
    }

    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Hunter Douglas Powerview Hub"
    assert result2["data"] == {"host": "1.2.3.4"}
    assert result2["result"].unique_id == "ABC123"

    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=discovery_info,
    )
    assert result3["type"] == "abort"


async def test_discovered_by_homekit_and_dhcp(hass: HomeAssistant) -> None:
    """Test we get the form with homekit and abort for dhcp source when we get both."""

    mock_powerview_userdata = _get_mock_powerview_userdata()
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=HOMEKIT_DISCOVERY_INFO,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "link"

    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY_INFO,
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_in_progress"


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerview_userdata = _get_mock_powerview_userdata(
        get_resources=asyncio.TimeoutError
    )
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_no_data(hass: HomeAssistant) -> None:
    """Test we handle no data being returned from the hub."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerview_userdata = _get_mock_powerview_userdata(userdata={"userData": {}})
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerview_userdata = _get_mock_powerview_userdata(userdata={"userData": {}})
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
