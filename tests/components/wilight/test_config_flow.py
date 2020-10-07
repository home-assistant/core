"""Test the WiLight config flow."""
from asynctest import patch
import pytest

from homeassistant.components.wilight.config_flow import (
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
)
from homeassistant.components.wilight.const import DOMAIN
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SOURCE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry
from tests.components.wilight import (
    CONF_COMPONENTS,
    HOST,
    MOCK_SSDP_DISCOVERY_INFO_LIGHT_FAN,
    MOCK_SSDP_DISCOVERY_INFO_MISSING_MANUFACTORER,
    MOCK_SSDP_DISCOVERY_INFO_P_B,
    MOCK_SSDP_DISCOVERY_INFO_WRONG_MANUFACTORER,
    UPNP_MODEL_NAME_P_B,
    UPNP_SERIAL,
    WILIGHT_ID,
)


@pytest.fixture(name="dummy_get_components_from_model_clear")
def mock_dummy_get_components_from_model():
    """Mock a clear components list."""
    components = []
    with patch(
        "pywilight.get_components_from_model",
        return_value=components,
    ):
        yield components


async def test_show_ssdp_form(hass: HomeAssistantType) -> None:
    """Test that the ssdp confirmation form is served."""

    discovery_info = MOCK_SSDP_DISCOVERY_INFO_P_B.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        CONF_NAME: f"WL{WILIGHT_ID}",
        CONF_COMPONENTS: "light",
    }


async def test_ssdp_not_wilight_abort_1(hass: HomeAssistantType) -> None:
    """Test that the ssdp aborts not_wilight."""

    discovery_info = MOCK_SSDP_DISCOVERY_INFO_WRONG_MANUFACTORER.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "not_wilight_device"


async def test_ssdp_not_wilight_abort_2(hass: HomeAssistantType) -> None:
    """Test that the ssdp aborts not_wilight."""

    discovery_info = MOCK_SSDP_DISCOVERY_INFO_MISSING_MANUFACTORER.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "not_wilight_device"


async def test_ssdp_not_wilight_abort_3(
    hass: HomeAssistantType, dummy_get_components_from_model_clear
) -> None:
    """Test that the ssdp aborts not_wilight."""

    discovery_info = MOCK_SSDP_DISCOVERY_INFO_P_B.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "not_wilight_device"


async def test_ssdp_not_supported_abort(hass: HomeAssistantType) -> None:
    """Test that the ssdp aborts not_supported."""

    discovery_info = MOCK_SSDP_DISCOVERY_INFO_LIGHT_FAN.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "not_supported_device"


async def test_ssdp_device_exists_abort(hass: HomeAssistantType) -> None:
    """Test abort SSDP flow if WiLight already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WILIGHT_ID,
        data={
            CONF_HOST: HOST,
            CONF_SERIAL_NUMBER: UPNP_SERIAL,
            CONF_MODEL_NAME: UPNP_MODEL_NAME_P_B,
        },
    )

    entry.add_to_hass(hass)

    discovery_info = MOCK_SSDP_DISCOVERY_INFO_P_B.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_full_ssdp_flow_implementation(hass: HomeAssistantType) -> None:
    """Test the full SSDP flow from start to finish."""

    discovery_info = MOCK_SSDP_DISCOVERY_INFO_P_B.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        CONF_NAME: f"WL{WILIGHT_ID}",
        "components": "light",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"WL{WILIGHT_ID}"

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_SERIAL_NUMBER] == UPNP_SERIAL
    assert result["data"][CONF_MODEL_NAME] == UPNP_MODEL_NAME_P_B
