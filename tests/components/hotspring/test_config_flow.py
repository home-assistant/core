"""Tests for the Hot Spring config flow."""

from unittest.mock import MagicMock

from hotspring import HotSpringConnectionError, HotSpringError, Spa, SpaBrand, SpaInfo
import pytest

from homeassistant.components.hotspring.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_hotspring")
async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["title"] == "ConnectedSpa_DDEEFF"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


@pytest.mark.usefixtures("mock_hotspring")
async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort the config flow if Hot Spring spa is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"


@pytest.mark.parametrize(
    "exception",
    [HotSpringConnectionError, HotSpringError],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect(
    hass: HomeAssistant, mock_hotspring: MagicMock, exception: type[Exception]
) -> None:
    """Test we show user form on Hot Spring connection error and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    mock_hotspring.update.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_hotspring.update.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["title"] == "ConnectedSpa_DDEEFF"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_no_mac_address(
    hass: HomeAssistant, mock_hotspring: MagicMock, device_fixture: Spa
) -> None:
    """Test we show user form on missing MAC address and recover."""
    valid_info = device_fixture.info
    device_fixture.info = SpaInfo(
        hostname="ConnectedSpa_DDEEFF",
        root_topic="unknownTopic123",
        sna_ready=True,
        brand=SpaBrand.HOTSPRING,
        brand_name="Hot Spring",
        collection="Highlife",
        model_name="Relay",
        brand_id="1",
        collection_id="1",
        model_id="1",
        volume=335,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    device_fixture.info = valid_info
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["title"] == "ConnectedSpa_DDEEFF"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"
