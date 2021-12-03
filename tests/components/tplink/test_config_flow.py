"""Test the tplink config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components import dhcp
from homeassistant.components.tplink import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_FORM

from . import (
    ALIAS,
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    MAC_ADDRESS,
    MODULE,
    _patch_discovery,
    _patch_single_discovery,
)

from tests.common import MockConfigEntry


async def test_discovery(hass: HomeAssistant):
    """Test setting up discovery."""
    with _patch_discovery(), _patch_single_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result2["type"] == "form"
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

        # test we can try again
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result2["type"] == "form"
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

    with _patch_discovery(), _patch_single_discovery(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MAC_ADDRESS},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == DEFAULT_ENTRY_TITLE
    assert result3["data"] == {CONF_HOST: IP_ADDRESS}
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_discovery_with_existing_device_present(hass: HomeAssistant):
    """Test setting up discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.2"}, unique_id="dd:dd:dd:dd:dd:dd"
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_single_discovery(no_device=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    # Now abort and make sure we can start over

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with _patch_discovery(), _patch_single_discovery(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: MAC_ADDRESS}
        )
        assert result3["type"] == "create_entry"
        assert result3["title"] == DEFAULT_ENTRY_TITLE
        assert result3["data"] == {
            CONF_HOST: IP_ADDRESS,
        }
        await hass.async_block_till_done()

    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_discovery_no_device(hass: HomeAssistant):
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_discovery(no_device=True), _patch_single_discovery():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_import(hass: HomeAssistant):
    """Test import from yaml."""
    config = {
        CONF_HOST: IP_ADDRESS,
    }

    # Cannot connect
    with _patch_discovery(no_device=True), _patch_single_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"

    # Success
    with _patch_discovery(), _patch_single_discovery(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_ENTRY_TITLE
    assert result["data"] == {
        CONF_HOST: IP_ADDRESS,
    }
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # Duplicate
    with _patch_discovery(), _patch_single_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_manual(hass: HomeAssistant):
    """Test manually setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Cannot connect (timeout)
    with _patch_discovery(no_device=True), _patch_single_discovery(no_device=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    # Success
    with _patch_discovery(), _patch_single_discovery(), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(f"{MODULE}.async_setup_entry", return_value=True):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()
    assert result4["type"] == "create_entry"
    assert result4["title"] == DEFAULT_ENTRY_TITLE
    assert result4["data"] == {
        CONF_HOST: IP_ADDRESS,
    }

    # Duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_discovery(no_device=True), _patch_single_discovery(no_device=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_manual_no_capabilities(hass: HomeAssistant):
    """Test manually setup without successful get_capabilities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(no_device=True), _patch_single_discovery(), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(f"{MODULE}.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_HOST: IP_ADDRESS,
    }


async def test_discovered_by_discovery_and_dhcp(hass):
    """Test we get the form with discovery and abort for dhcp source when we get both."""

    with _patch_discovery(), _patch_single_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DISCOVERY},
            data={CONF_HOST: IP_ADDRESS, CONF_MAC: MAC_ADDRESS, CONF_NAME: ALIAS},
        )
        await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_single_discovery():
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress=MAC_ADDRESS, hostname=ALIAS
            ),
        )
        await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_in_progress"

    with _patch_discovery(), _patch_single_discovery():
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress="00:00:00:00:00:00", hostname="mock_hostname"
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "already_in_progress"

    with _patch_discovery(no_device=True), _patch_single_discovery(no_device=True):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.2.3.5", macaddress="00:00:00:00:00:01", hostname="mock_hostname"
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    "source, data",
    [
        (
            config_entries.SOURCE_DHCP,
            dhcp.DhcpServiceInfo(ip=IP_ADDRESS, macaddress=MAC_ADDRESS, hostname=ALIAS),
        ),
        (
            config_entries.SOURCE_DISCOVERY,
            {CONF_HOST: IP_ADDRESS, CONF_MAC: MAC_ADDRESS, CONF_NAME: ALIAS},
        ),
    ],
)
async def test_discovered_by_dhcp_or_discovery(hass, source, data):
    """Test we can setup when discovered from dhcp or discovery."""

    with _patch_discovery(), _patch_single_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_single_discovery(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        CONF_HOST: IP_ADDRESS,
    }
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


@pytest.mark.parametrize(
    "source, data",
    [
        (
            config_entries.SOURCE_DHCP,
            dhcp.DhcpServiceInfo(ip=IP_ADDRESS, macaddress=MAC_ADDRESS, hostname=ALIAS),
        ),
        (
            config_entries.SOURCE_DISCOVERY,
            {CONF_HOST: IP_ADDRESS, CONF_MAC: MAC_ADDRESS, CONF_NAME: ALIAS},
        ),
    ],
)
async def test_discovered_by_dhcp_or_discovery_failed_to_get_device(hass, source, data):
    """Test we abort if we cannot get the unique id when discovered from dhcp."""

    with _patch_discovery(no_device=True), _patch_single_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


async def test_migration_device_online(hass: HomeAssistant):
    """Test migration from single config entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)
    config = {CONF_MAC: MAC_ADDRESS, CONF_NAME: ALIAS, CONF_HOST: IP_ADDRESS}

    with _patch_discovery(), _patch_single_discovery(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "migration"}, data=config
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == ALIAS
    assert result["data"] == {
        CONF_HOST: IP_ADDRESS,
    }
    assert len(mock_setup_entry.mock_calls) == 2

    # Duplicate
    with _patch_discovery(), _patch_single_discovery():
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "migration"}, data=config
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_migration_device_offline(hass: HomeAssistant):
    """Test migration from single config entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)
    config = {CONF_MAC: MAC_ADDRESS, CONF_NAME: ALIAS, CONF_HOST: None}

    with _patch_discovery(no_device=True), _patch_single_discovery(
        no_device=True
    ), patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry:
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "migration"}, data=config
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == ALIAS
    new_entry = result["result"]
    assert result["data"] == {
        CONF_HOST: None,
    }
    assert len(mock_setup_entry.mock_calls) == 2

    # Ensure a manual import updates the missing host
    config = {CONF_HOST: IP_ADDRESS}
    with _patch_discovery(no_device=True), _patch_single_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert new_entry.data[CONF_HOST] == IP_ADDRESS
