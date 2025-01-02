"""Define tests for the Flux LED/Magic Home config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.flux_led.config_flow import FluxLedConfigFlow
from homeassistant.components.flux_led.const import (
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    CONF_MINOR_VERSION,
    CONF_MODEL_DESCRIPTION,
    CONF_MODEL_INFO,
    CONF_MODEL_NUM,
    CONF_REMOTE_ACCESS_ENABLED,
    CONF_REMOTE_ACCESS_HOST,
    CONF_REMOTE_ACCESS_PORT,
    DOMAIN,
    TRANSITION_JUMP,
    TRANSITION_STROBE,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DEFAULT_ENTRY_TITLE,
    DHCP_DISCOVERY,
    FLUX_DISCOVERY,
    FLUX_DISCOVERY_PARTIAL,
    IP_ADDRESS,
    MAC_ADDRESS,
    MAC_ADDRESS_ONE_OFF,
    MODEL,
    MODEL_DESCRIPTION,
    MODEL_NUM,
    MODULE,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry

MAC_ADDRESS_DIFFERENT = "ff:bb:ff:dd:ee:ff"


async def test_discovery(hass: HomeAssistant) -> None:
    """Test setting up discovery."""
    with _patch_discovery(), _patch_wifibulb():
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
        _patch_wifibulb(),
        patch(f"{MODULE}.async_setup", return_value=True) as mock_setup,
        patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MAC_ADDRESS},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == DEFAULT_ENTRY_TITLE
    assert result3["data"] == {
        CONF_MINOR_VERSION: 4,
        CONF_HOST: IP_ADDRESS,
        CONF_MODEL: MODEL,
        CONF_MODEL_NUM: MODEL_NUM,
        CONF_MODEL_INFO: MODEL,
        CONF_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
        CONF_REMOTE_ACCESS_ENABLED: True,
        CONF_REMOTE_ACCESS_HOST: "the.cloud",
        CONF_REMOTE_ACCESS_PORT: 8816,
    }
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_discovery_legacy(hass: HomeAssistant) -> None:
    """Test setting up discovery with a legacy device."""
    with _patch_discovery(device=FLUX_DISCOVERY_PARTIAL), _patch_wifibulb():
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
        _patch_wifibulb(),
        patch(f"{MODULE}.async_setup", return_value=True) as mock_setup,
        patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MAC_ADDRESS},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == DEFAULT_ENTRY_TITLE
    assert result3["data"] == {
        CONF_MINOR_VERSION: 4,
        CONF_HOST: IP_ADDRESS,
        CONF_MODEL: MODEL,
        CONF_MODEL_NUM: MODEL_NUM,
        CONF_MODEL_INFO: MODEL,
        CONF_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
        CONF_REMOTE_ACCESS_ENABLED: True,
        CONF_REMOTE_ACCESS_HOST: "the.cloud",
        CONF_REMOTE_ACCESS_PORT: 8816,
    }
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_discovery_with_existing_device_present(hass: HomeAssistant) -> None:
    """Test setting up discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.2"}, unique_id="dd:dd:dd:dd:dd:dd"
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb(no_device=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_wifibulb():
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

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with (
        _patch_discovery(),
        _patch_wifibulb(),
        patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: MAC_ADDRESS}
        )
        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == DEFAULT_ENTRY_TITLE
        assert result3["data"] == {
            CONF_MINOR_VERSION: 4,
            CONF_HOST: IP_ADDRESS,
            CONF_MODEL: MODEL,
            CONF_MODEL_NUM: MODEL_NUM,
            CONF_MODEL_INFO: MODEL,
            CONF_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
            CONF_REMOTE_ACCESS_ENABLED: True,
            CONF_REMOTE_ACCESS_HOST: "the.cloud",
            CONF_REMOTE_ACCESS_PORT: 8816,
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

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_discovery_no_device(hass: HomeAssistant) -> None:
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_discovery(no_device=True), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_manual_working_discovery(hass: HomeAssistant) -> None:
    """Test manually setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Cannot connect (timeout)
    with _patch_discovery(no_device=True), _patch_wifibulb(no_device=True):
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
        _patch_wifibulb(),
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
        CONF_MINOR_VERSION: 4,
        CONF_HOST: IP_ADDRESS,
        CONF_MODEL: MODEL,
        CONF_MODEL_NUM: MODEL_NUM,
        CONF_MODEL_INFO: MODEL,
        CONF_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
        CONF_REMOTE_ACCESS_ENABLED: True,
        CONF_REMOTE_ACCESS_HOST: "the.cloud",
        CONF_REMOTE_ACCESS_PORT: 8816,
    }

    # Duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_discovery(no_device=True), _patch_wifibulb(no_device=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_manual_no_discovery_data(hass: HomeAssistant) -> None:
    """Test manually setup without discovery data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with (
        _patch_discovery(no_device=True),
        _patch_wifibulb(),
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
        CONF_MODEL_NUM: MODEL_NUM,
        CONF_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
    }


async def test_discovered_by_discovery_and_dhcp(hass: HomeAssistant) -> None:
    """Test we get the form with discovery and abort for dhcp source when we get both."""

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=FLUX_DISCOVERY,
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    real_is_matching = FluxLedConfigFlow.is_matching
    return_values = []

    def is_matching(self, other_flow) -> bool:
        return_values.append(real_is_matching(self, other_flow))
        return return_values[-1]

    with (
        _patch_discovery(),
        _patch_wifibulb(),
        patch.object(
            FluxLedConfigFlow, "is_matching", wraps=is_matching, autospec=True
        ),
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="any",
                ip=IP_ADDRESS,
                macaddress="000000000000",
            ),
        )
        await hass.async_block_till_done()

    # Ensure the is_matching method returned True
    assert return_values == [True]

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_in_progress"


async def test_discovered_by_discovery(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from discovery."""

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=FLUX_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        _patch_discovery(),
        _patch_wifibulb(),
        patch(f"{MODULE}.async_setup", return_value=True) as mock_async_setup,
        patch(
            f"{MODULE}.async_setup_entry", return_value=True
        ) as mock_async_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_MINOR_VERSION: 4,
        CONF_HOST: IP_ADDRESS,
        CONF_MODEL: MODEL,
        CONF_MODEL_NUM: MODEL_NUM,
        CONF_MODEL_INFO: MODEL,
        CONF_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
        CONF_REMOTE_ACCESS_ENABLED: True,
        CONF_REMOTE_ACCESS_HOST: "the.cloud",
        CONF_REMOTE_ACCESS_PORT: 8816,
    }
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


async def test_discovered_by_dhcp_udp_responds(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from dhcp but with udp response."""

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        _patch_discovery(),
        _patch_wifibulb(),
        patch(f"{MODULE}.async_setup", return_value=True) as mock_async_setup,
        patch(
            f"{MODULE}.async_setup_entry", return_value=True
        ) as mock_async_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_MINOR_VERSION: 4,
        CONF_HOST: IP_ADDRESS,
        CONF_MODEL: MODEL,
        CONF_MODEL_NUM: MODEL_NUM,
        CONF_MODEL_INFO: MODEL,
        CONF_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
        CONF_REMOTE_ACCESS_ENABLED: True,
        CONF_REMOTE_ACCESS_HOST: "the.cloud",
        CONF_REMOTE_ACCESS_PORT: 8816,
    }
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


async def test_discovered_by_dhcp_no_udp_response(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from dhcp but no udp response."""

    with _patch_discovery(no_device=True), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        _patch_discovery(no_device=True),
        _patch_wifibulb(),
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
        CONF_MODEL_NUM: MODEL_NUM,
        CONF_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
    }
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


async def test_discovered_by_dhcp_partial_udp_response_fallback_tcp(
    hass: HomeAssistant,
) -> None:
    """Test we can setup when discovered from dhcp but part of the udp response is missing."""

    with _patch_discovery(no_device=True), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        _patch_discovery(device=FLUX_DISCOVERY_PARTIAL),
        _patch_wifibulb(),
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
        CONF_MODEL_NUM: MODEL_NUM,
        CONF_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
    }
    assert result2["title"] == "Bulb RGBCW DDEEFF"
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


async def test_discovered_by_dhcp_no_udp_response_or_tcp_response(
    hass: HomeAssistant,
) -> None:
    """Test we can setup when discovered from dhcp but no udp response or tcp response."""

    with _patch_discovery(no_device=True), _patch_wifibulb(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, FLUX_DISCOVERY),
    ],
)
async def test_discovered_by_dhcp_or_discovery_adds_missing_unique_id(
    hass: HomeAssistant, source, data
) -> None:
    """Test we can setup when discovered from dhcp or discovery."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: IP_ADDRESS})
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == MAC_ADDRESS


async def test_mac_address_off_by_one_updated_via_discovery(
    hass: HomeAssistant,
) -> None:
    """Test the mac address is updated when its off by one from integration discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS_ONE_OFF
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=FLUX_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == MAC_ADDRESS


async def test_mac_address_off_by_one_not_updated_from_dhcp(
    hass: HomeAssistant,
) -> None:
    """Test the mac address is NOT updated when its off by one from dhcp discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS_ONE_OFF
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == MAC_ADDRESS_ONE_OFF


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, FLUX_DISCOVERY),
    ],
)
async def test_discovered_by_dhcp_or_discovery_mac_address_mismatch_host_already_configured(
    hass: HomeAssistant, source, data
) -> None:
    """Test we abort if the host is already configured but the mac does not match."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS_DIFFERENT
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == MAC_ADDRESS_DIFFERENT


async def test_options(hass: HomeAssistant) -> None:
    """Test options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS},
        title=IP_ADDRESS,
        options={
            CONF_CUSTOM_EFFECT_COLORS: "[255,0,0], [0,0,255]",
            CONF_CUSTOM_EFFECT_SPEED_PCT: 30,
            CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_STROBE,
        },
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb():
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    user_input = {
        CONF_CUSTOM_EFFECT_COLORS: "[0,0,255], [255,0,0]",
        CONF_CUSTOM_EFFECT_SPEED_PCT: 50,
        CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_JUMP,
    }
    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == user_input
    assert result2["data"] == config_entry.options
    assert hass.states.get("light.bulb_rgbcw_ddeeff") is not None


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, FLUX_DISCOVERY),
    ],
)
async def test_discovered_can_be_ignored(hass: HomeAssistant, source, data) -> None:
    """Test we abort if the mac was already ignored."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id=MAC_ADDRESS,
        source=config_entries.SOURCE_IGNORE,
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
