"""Test config flow."""

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.yamaha.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# SSDP Flows


async def test_ssdp_discovery_failed(hass: HomeAssistant) -> None:
    """Test when an SSDP discovered device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://127.0.0.1/desc.xml",
            upnp={
                ssdp.ATTR_UPNP_MODEL_NAME: "MC20",
                ssdp.ATTR_UPNP_SERIAL: "123456789",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
