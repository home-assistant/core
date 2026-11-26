"""Tests for EnOcean config flow."""

from unittest.mock import AsyncMock, Mock, patch

from enocean_async import EURID
from enocean_async.protocol.erp1.rorg import RORG
from enocean_async.protocol.erp1.telegram import ERP1Telegram
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_capture_events

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.enocean.config_flow import EnOceanFlowHandler
from homeassistant.components.enocean.const import (
    CONF_DEVICE_TYPE_ID,
    DEVICE_TYPE_ROCKER_SWITCH,
    DOMAIN,
    MANUFACTURER,
    SUBENTRY_TYPE_DEVICE,
)
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USB,
    SOURCE_USER,
    ConfigEntryState,
    ConfigSubentryData,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.usb import UsbServiceInfo

GATEWAY_CLASS = "homeassistant.components.enocean.config_flow.Gateway"
GLOB_METHOD = "homeassistant.components.enocean.config_flow.glob.glob"
SETUP_ENTRY_METHOD = "homeassistant.components.enocean.async_setup_entry"


async def test_user_flow_cannot_create_multiple_instances(hass: HomeAssistant) -> None:
    """Test that the user flow aborts if an instance is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/already/configured/path"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_flow_with_detected_dongle(hass: HomeAssistant) -> None:
    """Test the user flow with a detected EnOcean dongle."""
    FAKE_DONGLE_PATH = "/fake/dongle"

    with patch(GLOB_METHOD, side_effect=[[FAKE_DONGLE_PATH], [], []]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "detect"
    devices = result["data_schema"].schema.get(CONF_DEVICE).config.get("options")
    assert FAKE_DONGLE_PATH in devices
    assert EnOceanFlowHandler.MANUAL_PATH_VALUE in devices


async def test_user_flow_with_no_detected_dongle(hass: HomeAssistant) -> None:
    """Test the user flow with no detected EnOcean dongle."""
    with patch(GLOB_METHOD, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_detection_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the detection flow with a valid path selected."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(
        GATEWAY_CLASS,
        return_value=Mock(start=AsyncMock(), stop=AsyncMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "detect"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


async def test_detection_flow_with_custom_path(hass: HomeAssistant) -> None:
    """Test the detection flow with custom path selected."""
    USER_PROVIDED_PATH = EnOceanFlowHandler.MANUAL_PATH_VALUE

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "detect"},
        data={CONF_DEVICE: USER_PROVIDED_PATH},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_detection_flow_with_invalid_path(hass: HomeAssistant) -> None:
    """Test the detection flow with an invalid path selected."""
    USER_PROVIDED_PATH = "/invalid/path"

    with patch(
        GATEWAY_CLASS,
        return_value=Mock(
            start=AsyncMock(side_effect=ConnectionError("invalid path")),
            stop=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "detect"},
            data={CONF_DEVICE: USER_PROVIDED_PATH},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert CONF_DEVICE in result["errors"]

    with (
        patch(GATEWAY_CLASS, return_value=Mock(start=AsyncMock(), stop=AsyncMock())),
        patch(SETUP_ENTRY_METHOD, AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the manual flow with a valid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(
        GATEWAY_CLASS,
        return_value=Mock(start=AsyncMock(), stop=AsyncMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


async def test_manual_flow_with_invalid_path(hass: HomeAssistant) -> None:
    """Test the manual flow with an invalid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(
        GATEWAY_CLASS,
        return_value=Mock(
            start=AsyncMock(side_effect=ConnectionError("invalid path")),
            stop=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert CONF_DEVICE in result["errors"]

    with (
        patch(GATEWAY_CLASS, return_value=Mock(start=AsyncMock(), stop=AsyncMock())),
        patch(SETUP_ENTRY_METHOD, AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the import flow with a valid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/valid/path/to/import"}

    with patch(
        GATEWAY_CLASS,
        return_value=Mock(start=AsyncMock(), stop=AsyncMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == DATA_TO_IMPORT[CONF_DEVICE]


async def test_import_flow_with_invalid_path(hass: HomeAssistant) -> None:
    """Test the import flow with an invalid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/invalid/path/to/import"}

    with patch(
        GATEWAY_CLASS,
        return_value=Mock(
            start=AsyncMock(side_effect=ConnectionError("invalid path")),
            stop=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_dongle_path"


async def test_usb_discovery(
    hass: HomeAssistant,
) -> None:
    """Test usb discovery success path."""
    usb_discovery_info = UsbServiceInfo(
        device="/dev/enocean0",
        pid="6001",
        vid="0403",
        serial_number="1234",
        description="USB 300",
        manufacturer="EnOcean GmbH",
    )
    device = "/dev/enocean0"
    # test discovery step
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=usb_discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"
    assert result["errors"] is None

    # test device path
    with (
        patch(
            GATEWAY_CLASS,
            return_value=Mock(start=AsyncMock(), stop=AsyncMock()),
        ),
        patch(SETUP_ENTRY_METHOD, AsyncMock(return_value=None)),
        patch(
            "homeassistant.components.usb.get_serial_by_id",
            side_effect=lambda x: x,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MANUFACTURER
    assert result["data"] == {"device": device}
    assert result["context"]["unique_id"] == "0403:6001_1234_EnOcean GmbH_USB 300"
    assert result["context"]["title_placeholders"] == {
        "name": "USB 300 - /dev/enocean0, s/n: 1234 - EnOcean GmbH - 0403:6001"
    }
    assert result["result"].state is ConfigEntryState.LOADED


async def test_usb_discovery_already_configured_updates_path(
    hass: HomeAssistant,
) -> None:
    """Test usb discovery aborts when already configured and updates device path."""
    # Existing entry with the same unique_id but an old device path
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/enocean-old"},
        unique_id="0403:6001_1234_EnOcean GmbH_USB 300",
    )
    existing_entry.add_to_hass(hass)

    # New USB discovery for the same dongle but with an updated device path
    usb_discovery_info = UsbServiceInfo(
        device="/dev/enocean-new",
        pid="6001",
        vid="0403",
        serial_number="1234",
        description="USB 300",
        manufacturer="EnOcean GmbH",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=usb_discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def _start_add_device_flow(hass: HomeAssistant, config_entry: MockConfigEntry):
    """Set up the entry and start the flow that adds a device."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]
    return result


@pytest.mark.parametrize(
    "device_class",
    [
        pytest.param(None, id="without_device_class"),
        pytest.param("door", id="with_device_class"),
    ],
)
async def test_add_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: Mock,
    device_class: str | None,
) -> None:
    """Test that a rocker switch added in the UI gets its binary sensor."""
    options = {CONF_DEVICE_CLASS: device_class} if device_class else {}
    result = await _start_add_device_flow(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_ID: "de:ad:be:ef", **options},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry,) = mock_config_entry.subentries.values()
    assert subentry.subentry_type == SUBENTRY_TYPE_DEVICE
    assert subentry.title == "Rocker switch DE:AD:BE:EF"
    assert subentry.unique_id == "DE:AD:BE:EF"
    assert subentry.data == {
        CONF_ID: "DE:AD:BE:EF",
        CONF_DEVICE_TYPE_ID: DEVICE_TYPE_ROCKER_SWITCH,
        **options,
    }

    state = hass.states.get("binary_sensor.rocker_switch_de_ad_be_ef")
    assert state is not None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class

    events = async_capture_events(hass, "button_pressed")
    mock_gateway.add_erp1_received_callback.call_args.args[0](
        ERP1Telegram(RORG.RORG_RPS, b"\x70", EURID("DE:AD:BE:EF"), 0x30)
    )
    await hass.async_block_till_done()
    assert len(events) == 1

    # the gateway keeps running: the serial port is not closed and opened again
    assert mock_gateway.start.call_count == 1
    mock_gateway.stop.assert_not_called()


@pytest.mark.usefixtures("mock_gateway")
async def test_add_several_devices(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that every added device gets one binary sensor."""
    result = await _start_add_device_flow(hass, mock_config_entry)
    await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={CONF_ID: "DE:AD:BE:01"}
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": SOURCE_USER},
    )
    await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={CONF_ID: "DE:AD:BE:02"}
    )
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == [
        "binary_sensor.rocker_switch_de_ad_be_01",
        "binary_sensor.rocker_switch_de_ad_be_02",
    ]


@pytest.mark.parametrize(
    "device_id",
    [
        pytest.param("nonsense", id="no_address"),
        pytest.param("DE:AD:BE", id="three_bytes"),
        pytest.param("DE:AD:BE:EF:00", id="five_bytes"),
        pytest.param("GG:AD:BE:EF", id="no_hex"),
        pytest.param("DEADBEEF", id="no_colons"),
    ],
)
@pytest.mark.usefixtures("mock_gateway")
async def test_add_device_with_invalid_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, device_id: str
) -> None:
    """Test that an ID no EnOcean device can have is refused and can be corrected."""
    result = await _start_add_device_flow(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={CONF_ID: device_id}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ID: "invalid_device_id"}
    assert not mock_config_entry.subentries

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={CONF_ID: "DE:AD:BE:EF"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.states.get("binary_sensor.rocker_switch_de_ad_be_ef") is not None


@pytest.mark.parametrize(
    "device_id",
    [
        pytest.param("DE:AD:BE:EF", id="same_spelling"),
        pytest.param("de:ad:be:ef", id="lower_case"),
    ],
)
@pytest.mark.usefixtures("mock_gateway")
async def test_add_device_that_is_already_configured(
    hass: HomeAssistant, device_id: str
) -> None:
    """Test that a device cannot be added twice."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyUSB0"},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_ID: "DE:AD:BE:EF",
                    CONF_DEVICE_TYPE_ID: DEVICE_TYPE_ROCKER_SWITCH,
                },
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Existing",
                unique_id="DE:AD:BE:EF",
            )
        ],
    )
    result = await _start_add_device_flow(hass, config_entry)

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={CONF_ID: device_id}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ID: "already_configured_device"}
    assert len(config_entry.subentries) == 1

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={CONF_ID: "DE:AD:BE:01"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert sorted(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == [
        "binary_sensor.existing",
        "binary_sensor.rocker_switch_de_ad_be_01",
    ]
