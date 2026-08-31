"""Test the Qingping config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.qingping.const import (
    CONF_CONNECTION_TYPE,
    CONNECTION_MQTT,
    DOMAIN,
    MQTT_TOPIC_PREFIX,
)
from homeassistant.const import CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from . import (
    LIGHT_AND_SIGNAL_SERVICE_INFO,
    MQTT_MAC,
    MQTT_TLV_PAYLOAD,
    NO_DATA_SERVICE_INFO,
    NOT_QINGPING_SERVICE_INFO,
)

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def _async_start_bluetooth_user_flow(hass: HomeAssistant) -> FlowResult:
    """Start the user flow and choose the Bluetooth device path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "bluetooth_device"}
    )


async def _async_start_mqtt_user_flow(hass: HomeAssistant) -> FlowResult:
    """Start the user flow, choose the MQTT path and publish a device message."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU

    async def _fire_device_message(_: float) -> None:
        async_fire_mqtt_message(
            hass, f"{MQTT_TOPIC_PREFIX}/{MQTT_MAC.lower()}/up", MQTT_TLV_PAYLOAD
        )

    with (
        patch(
            "homeassistant.components.qingping.config_flow.MQTT_DISCOVERY_TIMEOUT",
            0,
        ),
        patch(
            "homeassistant.components.qingping.config_flow.asyncio.sleep",
            _fire_device_message,
        ),
    ):
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"next_step_id": "mqtt_device"}
        )


def _mac_options(result: FlowResult) -> list[str]:
    """Return the MAC addresses offered by the mqtt_device form."""
    mac_selector = next(
        value
        for key, value in result["data_schema"].schema.items()
        if key.schema == CONF_MAC
    )
    return [option["value"] for option in mac_selector.config["options"]]


async def test_async_step_bluetooth_valid_device(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LIGHT_AND_SIGNAL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    with patch(
        "homeassistant.components.qingping.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Motion & Light EEFF"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "aa:bb:cc:dd:ee:ff"


async def test_async_step_bluetooth_not_enough_info_at_start(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with only a partial adv at the start."""
    with patch(
        "homeassistant.components.qingping.config_flow.async_process_advertisements",
        return_value=LIGHT_AND_SIGNAL_SERVICE_INFO,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=NO_DATA_SERVICE_INFO,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    with patch(
        "homeassistant.components.qingping.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Qingping Motion & Light"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "aa:bb:cc:dd:ee:ff"


async def test_async_step_bluetooth_not_qingping(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth not qingping."""
    with patch(
        "homeassistant.components.qingping.config_flow.async_process_advertisements",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=NOT_QINGPING_SERVICE_INFO,
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_async_step_user_no_devices_found(hass: HomeAssistant) -> None:
    """Test setup from service info cache with no devices found."""
    result = await _async_start_bluetooth_user_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_with_found_devices(hass: HomeAssistant) -> None:
    """Test setup from service info cache with devices found."""
    with (
        patch(
            "homeassistant.components.qingping.config_flow.async_discovered_service_info",
            return_value=[LIGHT_AND_SIGNAL_SERVICE_INFO],
        ),
        patch(
            "homeassistant.components.qingping.config_flow.bluetooth.async_request_active_scan"
        ) as mock_request_active_scan,
    ):
        result = await _async_start_bluetooth_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_device"
    mock_request_active_scan.assert_awaited_once_with(hass)
    with patch(
        "homeassistant.components.qingping.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "aa:bb:cc:dd:ee:ff"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Motion & Light EEFF"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "aa:bb:cc:dd:ee:ff"


async def test_async_step_user_replace_ignored(hass: HomeAssistant) -> None:
    """Test setup from service info can replace an ignored entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=LIGHT_AND_SIGNAL_SERVICE_INFO.address,
        source=config_entries.SOURCE_IGNORE,
        data={},
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.qingping.config_flow.async_discovered_service_info",
        return_value=[LIGHT_AND_SIGNAL_SERVICE_INFO],
    ):
        result = await _async_start_bluetooth_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_device"
    with patch(
        "homeassistant.components.qingping.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "aa:bb:cc:dd:ee:ff"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Motion & Light EEFF"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "aa:bb:cc:dd:ee:ff"


async def test_async_step_user_device_added_between_steps(hass: HomeAssistant) -> None:
    """Test the device gets added via another flow between steps."""
    with patch(
        "homeassistant.components.qingping.config_flow.async_discovered_service_info",
        return_value=[LIGHT_AND_SIGNAL_SERVICE_INFO],
    ):
        result = await _async_start_bluetooth_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_device"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qingping.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "aa:bb:cc:dd:ee:ff"},
        )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_async_step_user_with_found_devices_already_setup(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qingping.config_flow.async_discovered_service_info",
        return_value=[LIGHT_AND_SIGNAL_SERVICE_INFO],
    ):
        result = await _async_start_bluetooth_user_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth_devices_already_setup(hass: HomeAssistant) -> None:
    """Test we can't start a flow if there is already a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LIGHT_AND_SIGNAL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LIGHT_AND_SIGNAL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LIGHT_AND_SIGNAL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_async_step_user_takes_precedence_over_discovery(
    hass: HomeAssistant,
) -> None:
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LIGHT_AND_SIGNAL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "homeassistant.components.qingping.config_flow.async_discovered_service_info",
        return_value=[LIGHT_AND_SIGNAL_SERVICE_INFO],
    ):
        result = await _async_start_bluetooth_user_flow(hass)
        assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.qingping.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "aa:bb:cc:dd:ee:ff"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Motion & Light EEFF"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "aa:bb:cc:dd:ee:ff"

    # Verify the original one was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def test_async_step_user_menu_options(hass: HomeAssistant) -> None:
    """Test the user step offers both connection types."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {"bluetooth_device", "mqtt_device"}


async def test_async_step_mqtt_device_not_configured(hass: HomeAssistant) -> None:
    """Test the MQTT path aborts when the MQTT integration is not set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "mqtt_device"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_configured"


async def test_async_step_mqtt_device_discovered(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test a device publishing on MQTT is offered and creates an entry."""
    result = await _async_start_mqtt_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt_device"
    assert MQTT_MAC in _mac_options(result)

    with patch(
        "homeassistant.components.qingping.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"Qingping Indoor Environment Monitor ({MQTT_MAC})"
    assert result2["data"] == {
        CONF_CONNECTION_TYPE: CONNECTION_MQTT,
        CONF_MAC: MQTT_MAC,
        CONF_MODEL: "cgr1w",
    }
    assert result2["result"].unique_id == MQTT_MAC


async def test_async_step_mqtt_device_invalid_mac(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test manual MAC entry rejects an invalid address."""
    result = await _async_start_mqtt_user_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAC: "not-a-mac", CONF_MODEL: "cgr1w"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "mqtt_device"
    assert result2["errors"] == {CONF_MAC: "invalid_mac"}

    with patch(
        "homeassistant.components.qingping.async_setup_entry", return_value=True
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={CONF_MAC: "58:2d:34:12:a4:c2", CONF_MODEL: "cgr1w"},
        )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_MAC] == MQTT_MAC


async def test_async_step_mqtt_device_already_configured(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test a device that is already set up is not offered again."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MQTT_MAC,
        data={
            CONF_CONNECTION_TYPE: CONNECTION_MQTT,
            CONF_MAC: MQTT_MAC,
            CONF_MODEL: "cgr1w",
        },
    )
    entry.add_to_hass(hass)

    result = await _async_start_mqtt_user_flow(hass)
    assert MQTT_MAC not in _mac_options(result)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
