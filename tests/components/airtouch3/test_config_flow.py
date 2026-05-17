"""Test the AirTouch 3 Air Conditioner config flow."""

from dataclasses import asdict
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.airtouch3.comms.airtouch_aircon import Aircon
from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.components.airtouch3.discovery import AirTouch3Discovery
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

SYSTEM_ID = "35901813"


def _aircon(system_id: str = SYSTEM_ID) -> Aircon:
    """Create AirTouch data for config flow tests."""
    aircon = Aircon(1)
    aircon.system_id = system_id
    return aircon


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=_aircon(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "AirTouch 3 Air Conditioner"
    assert result["result"].unique_id == SYSTEM_ID
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        side_effect=UpdateFailed("failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=_aircon(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "AirTouch 3 Air Conditioner"
    assert result["result"].unique_id == SYSTEM_ID
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if the host is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=_aircon(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == SYSTEM_ID


async def test_user_search_pick_device(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test leaving host blank discovers and configures a controller."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    discovery = AirTouch3Discovery(
        host="1.1.1.1", mac="F0FE6B772324", model="AirTouch3"
    )
    with (
        patch(
            "homeassistant.components.airtouch3.config_flow.async_discover_devices",
            return_value=[discovery],
        ),
        patch(
            "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
            return_value=_aircon(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: ""}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pick_device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": SYSTEM_ID}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SYSTEM_ID
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_search_no_devices_found(hass: HomeAssistant) -> None:
    """Test discovery search falls back to the manual host form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_discover_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: ""}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_devices_found"}


async def test_integration_discovery_confirm(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery creates a confirm flow."""
    discovery = AirTouch3Discovery(
        host="1.1.1.1", mac="F0FE6B772324", model="AirTouch3"
    )
    with (
        patch(
            "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
            return_value=_aircon(),
        ),
        patch(
            "homeassistant.components.airtouch3.config_flow.onboarding.async_is_onboarded",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=asdict(discovery),
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SYSTEM_ID
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_integration_discovery_updates_host(hass: HomeAssistant) -> None:
    """Test discovery updates the host for an existing controller."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SYSTEM_ID, data={CONF_HOST: "1.1.1.1"}
    )
    entry.add_to_hass(hass)
    discovery = AirTouch3Discovery(
        host="2.2.2.2", mac="F0FE6B772324", model="AirTouch3"
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=_aircon(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=asdict(discovery),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: "2.2.2.2"}


async def test_dhcp_discovery_confirm(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test DHCP discovery creates a confirm flow."""
    discovery_info = DhcpServiceInfo(
        ip="1.1.1.1", hostname="airtouch3", macaddress="f0fe6b772324"
    )
    with (
        patch(
            "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
            return_value=_aircon(),
        ),
        patch(
            "homeassistant.components.airtouch3.config_flow.onboarding.async_is_onboarded",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SYSTEM_ID
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_updates_host(hass: HomeAssistant) -> None:
    """Test DHCP discovery updates the host for an existing controller."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SYSTEM_ID, data={CONF_HOST: "1.1.1.1"}
    )
    entry.add_to_hass(hass)
    discovery_info = DhcpServiceInfo(
        ip="2.2.2.2", hostname="airtouch3", macaddress="f0fe6b772324"
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=_aircon(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: "2.2.2.2"}


async def test_dhcp_discovery_cannot_connect(hass: HomeAssistant) -> None:
    """Test DHCP discovery aborts when validation fails."""
    discovery_info = DhcpServiceInfo(
        ip="1.1.1.1", hostname="airtouch3", macaddress="f0fe6b772324"
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        side_effect=UpdateFailed("failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_updates_host(hass: HomeAssistant) -> None:
    """Test reconfiguring the host."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=_aircon(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: " 2.2.2.2 ",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_HOST: "2.2.2.2",
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(UpdateFailed("failed"), "cannot_connect", id="cannot-connect"),
        pytest.param(RuntimeError("boom"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_errors(
    hass: HomeAssistant,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reconfigure error handling."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2.2.2.2",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=_aircon(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2.2.2.2",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
