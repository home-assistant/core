"""Tests for the lifx integration config flow."""

from ipaddress import ip_address
import socket
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.config_flow import LifXConfigFlow
from homeassistant.components.lifx.const import CONF_SERIAL
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    DHCP_FORMATTED_MAC,
    IP_ADDRESS,
    LABEL,
    MODULE,
    SERIAL,
    _mocked_bulb,
    _mocked_failing_bulb,
    _mocked_relay,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry


async def test_discovery(hass: HomeAssistant) -> None:
    """Test setting up discovery."""
    with _patch_discovery(), _patch_config_flow_try_connect():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

        # test we can try again
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

    with (
        _patch_discovery(),
        _patch_config_flow_try_connect(),
        patch(f"{MODULE}.async_setup", return_value=True) as mock_setup,
        patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: SERIAL},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == DEFAULT_ENTRY_TITLE
    assert result3["data"] == {CONF_HOST: IP_ADDRESS}
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_config_flow_try_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_discovery_but_cannot_connect(hass: HomeAssistant) -> None:
    """Test we can discover the device but we cannot connect."""
    with _patch_discovery(), _patch_config_flow_try_connect(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: SERIAL},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "cannot_connect"


async def test_discovery_with_existing_device_present(hass: HomeAssistant) -> None:
    """Test setting up discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.2"}, unique_id="dd:dd:dd:dd:dd:dd"
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_config_flow_try_connect(no_device=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_config_flow_try_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    # Now abort and make sure we can start over

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_config_flow_try_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with (
        _patch_discovery(),
        _patch_config_flow_try_connect(),
        patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: SERIAL}
        )
        assert result3["type"] is FlowResultType.CREATE_ENTRY
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_config_flow_try_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_discovery_no_device(hass: HomeAssistant) -> None:
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        _patch_discovery(no_device=True),
        _patch_config_flow_try_connect(no_device=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_manual(hass: HomeAssistant) -> None:
    """Test manually setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Cannot connect (timeout)
    with (
        _patch_discovery(no_device=True),
        _patch_config_flow_try_connect(no_device=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    # Success
    with (
        _patch_discovery(),
        _patch_config_flow_try_connect(),
        patch(f"{MODULE}.async_setup", return_value=True),
        patch(f"{MODULE}.async_setup_entry", return_value=True),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == DEFAULT_ENTRY_TITLE
    assert result4["data"] == {
        CONF_HOST: IP_ADDRESS,
    }

    # Duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        _patch_discovery(no_device=True),
        _patch_config_flow_try_connect(no_device=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_manual_dns_error(hass: HomeAssistant) -> None:
    """Test manually setup with unresolving host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    class MockLifxConnectonDnsError:
        """Mock lifx discovery."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Init connection."""
            self.device = _mocked_failing_bulb()

        async def async_setup(self):
            """Mock setup."""
            raise socket.gaierror

        def async_stop(self):
            """Mock teardown."""

    # Cannot connect due to dns error
    with (
        _patch_discovery(no_device=True),
        patch(
            "homeassistant.components.lifx.config_flow.LIFXConnection",
            MockLifxConnectonDnsError,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "does.not.resolve"}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_manual_no_capabilities(hass: HomeAssistant) -> None:
    """Test manually setup without successful get_capabilities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with (
        _patch_discovery(no_device=True),
        _patch_config_flow_try_connect(),
        patch(f"{MODULE}.async_setup", return_value=True),
        patch(f"{MODULE}.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: IP_ADDRESS,
    }


async def test_discovered_by_discovery_and_dhcp(hass: HomeAssistant) -> None:
    """Test we get the form with discovery and abort for dhcp source when we get both."""

    with _patch_discovery(), _patch_config_flow_try_connect():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_config_flow_try_connect():
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress=DHCP_FORMATTED_MAC, hostname=LABEL
            ),
        )
        await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    real_is_matching = LifXConfigFlow.is_matching
    return_values = []

    def is_matching(self, other_flow) -> bool:
        return_values.append(real_is_matching(self, other_flow))
        return return_values[-1]

    with (
        _patch_discovery(),
        _patch_config_flow_try_connect(),
        patch.object(LifXConfigFlow, "is_matching", wraps=is_matching, autospec=True),
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress="000000000000", hostname="mock_hostname"
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_in_progress"
    # Ensure the is_matching method returned True
    assert return_values == [True]

    with (
        _patch_discovery(no_device=True),
        _patch_config_flow_try_connect(no_device=True),
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                ip="1.2.3.5", macaddress="000000000001", hostname="mock_hostname"
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (
            config_entries.SOURCE_DHCP,
            DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress=DHCP_FORMATTED_MAC, hostname=LABEL
            ),
        ),
        (
            config_entries.SOURCE_HOMEKIT,
            ZeroconfServiceInfo(
                ip_address=ip_address(IP_ADDRESS),
                ip_addresses=[ip_address(IP_ADDRESS)],
                hostname=LABEL,
                name=LABEL,
                port=None,
                properties={ATTR_PROPERTIES_ID: "any"},
                type="mock_type",
            ),
        ),
        (
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
        ),
    ],
)
async def test_discovered_by_dhcp_or_discovery(
    hass: HomeAssistant, source, data
) -> None:
    """Test we can setup when discovered from dhcp or discovery."""

    with _patch_discovery(), _patch_config_flow_try_connect():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        _patch_discovery(),
        _patch_config_flow_try_connect(),
        patch(f"{MODULE}.async_setup", return_value=True) as mock_async_setup,
        patch(
            f"{MODULE}.async_setup_entry", return_value=True
        ) as mock_async_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: IP_ADDRESS,
    }
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (
            config_entries.SOURCE_DHCP,
            DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress=DHCP_FORMATTED_MAC, hostname=LABEL
            ),
        ),
        (
            config_entries.SOURCE_HOMEKIT,
            ZeroconfServiceInfo(
                ip_address=ip_address(IP_ADDRESS),
                ip_addresses=[ip_address(IP_ADDRESS)],
                hostname=LABEL,
                name=LABEL,
                port=None,
                properties={ATTR_PROPERTIES_ID: "any"},
                type="mock_type",
            ),
        ),
        (
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
        ),
    ],
)
async def test_discovered_by_dhcp_or_discovery_failed_to_get_device(
    hass: HomeAssistant, source, data
) -> None:
    """Test we abort if we cannot get the unique id when discovered from dhcp."""

    with (
        _patch_discovery(no_device=True),
        _patch_config_flow_try_connect(no_device=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (
            config_entries.SOURCE_DHCP,
            DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress=DHCP_FORMATTED_MAC, hostname=LABEL
            ),
        ),
        (
            config_entries.SOURCE_HOMEKIT,
            ZeroconfServiceInfo(
                ip_address=ip_address(IP_ADDRESS),
                ip_addresses=[ip_address(IP_ADDRESS)],
                hostname=LABEL,
                name=LABEL,
                port=None,
                properties={ATTR_PROPERTIES_ID: "any"},
                type="mock_type",
            ),
        ),
    ],
)
async def test_discovered_by_dhcp_or_homekit_updates_ip(
    hass: HomeAssistant, source, data
) -> None:
    """Update host from dhcp."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.2"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_config_flow_try_connect():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=data,
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == IP_ADDRESS


async def test_refuse_relays(hass: HomeAssistant) -> None:
    """Test we refuse to setup relays."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with (
        _patch_discovery(device=_mocked_relay()),
        _patch_config_flow_try_connect(device=_mocked_relay()),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_suggested_area(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test suggested area is populated from lifx group label."""

    class MockLifxCommandGetGroup:
        """Mock the get_group method that gets the group name from the bulb."""

        def __init__(self, bulb, **kwargs: Any) -> None:
            """Init command."""
            self.bulb = bulb
            self.lifx_group = kwargs.get("lifx_group")

        def __call__(self, callb=None, *args, **kwargs):
            """Call command."""
            self.bulb.group = self.lifx_group
            if callb:
                callb(self.bulb, self.lifx_group)

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "1.2.3.4"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.group = None
    bulb.get_group = MockLifxCommandGetGroup(bulb, lifx_group="My LIFX Group")

    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    entity = entity_registry.async_get(entity_id)

    device = device_registry.async_get(entity.device_id)
    assert device.suggested_area == "My LIFX Group"
