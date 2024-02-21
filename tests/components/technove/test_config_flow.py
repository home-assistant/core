"""Tests for the TechnoVE config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

import pytest
from technove import TechnoVEConnectionError

from homeassistant.components import zeroconf
from homeassistant.components.technove.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_technove")
async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
    )

    assert result.get("title") == "TechnoVE Station"
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.123"
    assert "result" in result
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"


@pytest.mark.usefixtures("mock_technove")
async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_technove: MagicMock,
) -> None:
    """Test we abort the config flow if TechnoVE station is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.123"},
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_connection_error(hass: HomeAssistant, mock_technove: MagicMock) -> None:
    """Test we show user form on TechnoVE connection error."""
    mock_technove.update.side_effect = TechnoVEConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "example.com"},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_technove")
async def test_full_user_flow_with_error(
    hass: HomeAssistant, mock_technove: MagicMock
) -> None:
    """Test the full manual user flow from start to finish with some errors in the middle."""
    mock_technove.update.side_effect = TechnoVEConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}

    mock_technove.update.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
    )

    assert result.get("title") == "TechnoVE Station"
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.123"
    assert "result" in result
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"


@pytest.mark.usefixtures("mock_setup_entry", "mock_technove")
async def test_full_zeroconf_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.123"),
            ip_addresses=[ip_address("192.168.1.123")],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "AA:AA:AA:AA:AA:BB"},
            type="mock_type",
        ),
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    assert result.get("description_placeholders") == {CONF_NAME: "TechnoVE Station"}
    assert result.get("step_id") == "zeroconf_confirm"
    assert result.get("type") == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2.get("title") == "TechnoVE Station"
    assert result2.get("type") == FlowResultType.CREATE_ENTRY

    assert "data" in result2
    assert result2["data"][CONF_HOST] == "192.168.1.123"
    assert "result" in result2
    assert result2["result"].unique_id == "AA:AA:AA:AA:AA:BB"


@pytest.mark.usefixtures("mock_technove")
async def test_zeroconf_during_onboarding(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_onboarding: MagicMock,
) -> None:
    """Test we create a config entry when discovered during onboarding."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.123"),
            ip_addresses=[ip_address("192.168.1.123")],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "AA:AA:AA:AA:AA:BB"},
            type="mock_type",
        ),
    )

    assert result.get("title") == "TechnoVE Station"
    assert result.get("type") == FlowResultType.CREATE_ENTRY

    assert result.get("data") == {CONF_HOST: "192.168.1.123"}
    assert "result" in result
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_zeroconf_connection_error(
    hass: HomeAssistant, mock_technove: MagicMock
) -> None:
    """Test we abort zeroconf flow on TechnoVE connection error."""
    mock_technove.update.side_effect = TechnoVEConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.123"),
            ip_addresses=[ip_address("192.168.1.123")],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "AA:AA:AA:AA:AA:BB"},
            type="mock_type",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


@pytest.mark.usefixtures("mock_technove")
async def test_user_station_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort zeroconf flow if TechnoVE station already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.123"},
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("mock_technove")
async def test_zeroconf_without_mac_station_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort zeroconf flow if TechnoVE station already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.123"),
            ip_addresses=[ip_address("192.168.1.123")],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("mock_technove")
async def test_zeroconf_with_mac_station_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_technove: MagicMock
) -> None:
    """Test we abort zeroconf flow if TechnoVE station already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.123"),
            ip_addresses=[ip_address("192.168.1.123")],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "AA:AA:AA:AA:AA:BB"},
            type="mock_type",
        ),
    )

    mock_technove.update.assert_not_called()
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
