"""Tests for the Heos config flow module."""

from pyheos import HeosError

from homeassistant.components import heos, ssdp
from homeassistant.components.heos.const import DATA_DISCOVERED_HOSTS, DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_flow_aborts_already_setup(hass: HomeAssistant, config_entry) -> None:
    """Test flow aborts when entry already setup."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_no_host_shows_form(hass: HomeAssistant) -> None:
    """Test form is shown when host not provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_cannot_connect_shows_error_form(hass: HomeAssistant, controller) -> None:
    """Test form is shown with error when cannot connect."""
    controller.connect.side_effect = HeosError()
    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "127.0.0.1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"][CONF_HOST] == "cannot_connect"
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1


async def test_create_entry_when_host_valid(hass: HomeAssistant, controller) -> None:
    """Test result type is create entry when host is valid."""
    data = {CONF_HOST: "127.0.0.1"}

    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_USER}, data=data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["title"] == "Controller (127.0.0.1)"
    assert result["data"] == data
    assert controller.connect.call_count == 2  # Also called in async_setup_entry
    assert controller.disconnect.call_count == 1


async def test_create_entry_when_friendly_name_valid(
    hass: HomeAssistant, controller
) -> None:
    """Test result type is create entry when friendly name is valid."""
    hass.data[DATA_DISCOVERED_HOSTS] = {"Office (127.0.0.1)": "127.0.0.1"}
    data = {CONF_HOST: "Office (127.0.0.1)"}

    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_USER}, data=data
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["title"] == "Controller (127.0.0.1)"
    assert result["data"] == {CONF_HOST: "127.0.0.1"}
    assert controller.connect.call_count == 2  # Also called in async_setup_entry
    assert controller.disconnect.call_count == 1
    assert DATA_DISCOVERED_HOSTS not in hass.data


async def test_discovery_shows_create_form(
    hass: HomeAssistant,
    controller,
    discovery_data: ssdp.SsdpServiceInfo,
    discovery_data_bedroom: ssdp.SsdpServiceInfo,
) -> None:
    """Test discovery shows form to confirm setup."""

    # Single discovered host shows form for user to finish setup.
    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data
    )
    assert hass.data[DATA_DISCOVERED_HOSTS] == {"Office (127.0.0.1)": "127.0.0.1"}
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Subsequent discovered hosts append to discovered hosts and abort.
    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data_bedroom
    )
    assert hass.data[DATA_DISCOVERED_HOSTS] == {
        "Office (127.0.0.1)": "127.0.0.1",
        "Bedroom (127.0.0.2)": "127.0.0.2",
    }
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_discovery_flow_aborts_already_setup(
    hass: HomeAssistant, controller, discovery_data: ssdp.SsdpServiceInfo, config_entry
) -> None:
    """Test discovery flow aborts when entry already setup."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
