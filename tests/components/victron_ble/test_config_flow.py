"""Test the Victron Bluetooth Low Energy config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.victron_ble.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .fixtures import (
    NOT_VICTRON_SERVICE_INFO,
    VICTRON_INVERTER_SERVICE_INFO,
    VICTRON_TEST_WRONG_TOKEN,
    VICTRON_VEBUS_SERVICE_INFO,
    VICTRON_VEBUS_TOKEN,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Mock bluetooth for all tests in this module."""


async def test_async_step_bluetooth_valid_device(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VICTRON_VEBUS_SERVICE_INFO,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "access_token"

    # test valid access token
    with patch(
        "homeassistant.components.victron_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ACCESS_TOKEN: VICTRON_VEBUS_TOKEN},
        )
    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == VICTRON_VEBUS_SERVICE_INFO.name
    flow_result = result2.get("result")
    assert flow_result is not None
    assert flow_result.unique_id == VICTRON_VEBUS_SERVICE_INFO.address


async def test_async_step_bluetooth_not_victron(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth not a victron device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_VICTRON_SERVICE_INFO,
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"


async def test_async_step_bluetooth_unsupported_by_library(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth of a victron device unsupported by the underlying library."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VICTRON_INVERTER_SERVICE_INFO,
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"


async def test_async_step_user_no_devices_found(hass: HomeAssistant) -> None:
    """Test setup from service info cache with no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "no_devices_found"


async def test_async_step_user_with_devices_found(hass: HomeAssistant) -> None:
    """Test setup from service info cache with devices found."""
    with patch(
        "homeassistant.components.victron_ble.config_flow.async_discovered_service_info",
        return_value=[VICTRON_VEBUS_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: VICTRON_VEBUS_SERVICE_INFO.address},
    )
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "access_token"

    # test invalid access token (valid already tested above)
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], user_input={CONF_ACCESS_TOKEN: VICTRON_TEST_WRONG_TOKEN}
    )
    assert result3.get("type") == FlowResultType.ABORT
    assert result3.get("reason") == "invalid_access_token"


async def test_async_step_user_device_added_between_steps(hass: HomeAssistant) -> None:
    """Test the device gets added via another flow between steps."""
    with patch(
        "homeassistant.components.victron_ble.config_flow.async_discovered_service_info",
        return_value=[VICTRON_VEBUS_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=VICTRON_VEBUS_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victron_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": VICTRON_VEBUS_SERVICE_INFO.address},
        )
    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"


async def test_async_step_user_with_found_devices_already_setup(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=VICTRON_VEBUS_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victron_ble.config_flow.async_discovered_service_info",
        return_value=[VICTRON_VEBUS_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "no_devices_found"


async def test_async_step_bluetooth_devices_already_setup(hass: HomeAssistant) -> None:
    """Test we can't start a flow if there is already a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=VICTRON_VEBUS_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VICTRON_VEBUS_SERVICE_INFO,
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VICTRON_VEBUS_SERVICE_INFO,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "access_token"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VICTRON_VEBUS_SERVICE_INFO,
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_in_progress"
