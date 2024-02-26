"""Test the Steamist config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.steamist.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DEFAULT_ENTRY_DATA,
    DEVICE_30303_NOT_STEAMIST,
    DEVICE_HOSTNAME,
    DEVICE_IP_ADDRESS,
    DEVICE_MAC_ADDRESS,
    DEVICE_NAME,
    DISCOVERY_30303,
    FORMATTED_MAC_ADDRESS,
    MOCK_ASYNC_GET_STATUS_INACTIVE,
    _patch_discovery,
    _patch_status,
)

from tests.common import MockConfigEntry

MODULE = "homeassistant.components.steamist"


DHCP_DISCOVERY = dhcp.DhcpServiceInfo(
    hostname=DEVICE_HOSTNAME,
    ip=DEVICE_IP_ADDRESS,
    macaddress=DEVICE_MAC_ADDRESS,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with _patch_discovery(no_device=True), patch(
        "homeassistant.components.steamist.config_flow.Steamist.async_get_status"
    ), patch(
        "homeassistant.components.steamist.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "127.0.0.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "127.0.0.1"
    assert result2["data"] == {
        "host": "127.0.0.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_discovery(hass: HomeAssistant) -> None:
    """Test we can also discovery the device during manual setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with _patch_discovery(), patch(
        "homeassistant.components.steamist.config_flow.Steamist.async_get_status"
    ), patch(
        "homeassistant.components.steamist.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "127.0.0.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == DEVICE_NAME
    assert result2["data"] == DEFAULT_ENTRY_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.steamist.config_flow.Steamist.async_get_status",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "127.0.0.1",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.steamist.config_flow.Steamist.async_get_status",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "127.0.0.1",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_discovery(hass: HomeAssistant) -> None:
    """Test setting up discovery."""
    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

        # test we can try again
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result2["type"] == "form"
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: FORMATTED_MAC_ADDRESS},
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == DEVICE_NAME
    assert result3["data"] == DEFAULT_ENTRY_DATA
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_discovered_by_discovery_and_dhcp(hass: HomeAssistant) -> None:
    """Test we get the form with discovery and abort for dhcp source when we get both."""

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=DISCOVERY_30303,
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="any",
                ip=DEVICE_IP_ADDRESS,
                macaddress="00:00:00:00:00:00",
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "already_in_progress"


async def test_discovered_by_discovery(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from discovery."""

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=DISCOVERY_30303,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == DEFAULT_ENTRY_DATA
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


async def test_discovered_by_dhcp(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from dhcp."""

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == DEFAULT_ENTRY_DATA
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


async def test_discovered_by_dhcp_discovery_fails(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from dhcp but then we cannot get the device name."""

    with _patch_discovery(no_device=True), _patch_status(
        MOCK_ASYNC_GET_STATUS_INACTIVE
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_discovered_by_dhcp_discovery_finds_non_steamist_device(
    hass: HomeAssistant,
) -> None:
    """Test we can setup when discovered from dhcp but its not a steamist device."""

    with _patch_discovery(device=DEVICE_30303_NOT_STEAMIST), _patch_status(
        MOCK_ASYNC_GET_STATUS_INACTIVE
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_steamist_device"


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, DISCOVERY_30303),
    ],
)
async def test_discovered_by_dhcp_or_discovery_adds_missing_unique_id(
    hass: HomeAssistant, source, data
) -> None:
    """Test we can setup when discovered from dhcp or discovery and add a missing unique id."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: DEVICE_IP_ADDRESS})
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == FORMATTED_MAC_ADDRESS
    assert mock_setup.called
    assert mock_setup_entry.called


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, DISCOVERY_30303),
    ],
)
async def test_discovered_by_dhcp_or_discovery_existing_unique_id_does_not_reload(
    hass: HomeAssistant, source, data
) -> None:
    """Test we can setup when discovered from dhcp or discovery and it does not reload."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=DEFAULT_ENTRY_DATA, unique_id=FORMATTED_MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert not mock_setup.called
    assert not mock_setup_entry.called
