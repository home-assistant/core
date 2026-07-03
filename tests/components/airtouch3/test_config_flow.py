"""Test the AirTouch 3 Air Conditioner config flow."""

from unittest.mock import AsyncMock, patch

from pyairtouch3 import AirTouchError
from pyairtouch3.airtouch_aircon import Aircon
import pytest

from homeassistant import config_entries
from homeassistant.components.airtouch3.config_flow import CannotConnect, validate_input
from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

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
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.airtouch3.config_flow.validate_input",
        return_value=SYSTEM_ID,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
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
        "homeassistant.components.airtouch3.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.airtouch3.config_flow.validate_input",
        return_value=SYSTEM_ID,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AirTouch 3 Air Conditioner"
    assert result["result"].unique_id == SYSTEM_ID
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_validate_input_without_system_id_raises_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test we handle a response without a system id as a connection error."""
    fetch_aircon = AsyncMock(return_value=_aircon(""))

    with patch(
        "homeassistant.components.airtouch3.config_flow.AirTouchClient"
    ) as client:
        client.return_value.fetch_aircon = fetch_aircon
        with pytest.raises(CannotConnect):
            await validate_input(hass, {CONF_HOST: "1.1.1.1"})

    fetch_aircon.assert_awaited_once()


async def test_validate_input_airtouch_error_raises_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test pyairtouch3 errors are handled as connection failures."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.AirTouchClient"
    ) as client:
        client.return_value.fetch_aircon = AsyncMock(
            side_effect=AirTouchError("closed")
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.1.1.1"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.validate_input",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if the host is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SYSTEM_ID, data={CONF_HOST: "1.1.1.1"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.validate_input",
        return_value=SYSTEM_ID,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_confirm(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test DHCP discovery creates a confirm flow."""
    discovery_info = DhcpServiceInfo(
        ip="1.1.1.1", hostname="airtouch3", macaddress="f0fe6b772324"
    )
    with (
        patch(
            "homeassistant.components.airtouch3.config_flow.validate_input",
            return_value=SYSTEM_ID,
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
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
        "homeassistant.components.airtouch3.config_flow.validate_input",
        return_value=SYSTEM_ID,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=discovery_info,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: "2.2.2.2"}


async def test_dhcp_discovery_cannot_connect(hass: HomeAssistant) -> None:
    """Test DHCP discovery aborts when validation fails."""
    discovery_info = DhcpServiceInfo(
        ip="1.1.1.1", hostname="airtouch3", macaddress="f0fe6b772324"
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=discovery_info,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
