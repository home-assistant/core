"""Tests for 1-Wire config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from pyownet import protocol
import pytest

from homeassistant.components.onewire.const import (
    DOMAIN,
    INPUT_ENTRY_CLEAR_OPTIONS,
    INPUT_ENTRY_DEVICE_SELECTION,
    MANUFACTURER_MAXIM,
)
from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

_HASSIO_DISCOVERY = HassioServiceInfo(
    config={"host": "1302b8e0-owserver", "port": 4304, "addon": "owserver (1-wire)"},
    name="owserver (1-wire)",
    slug="1302b8e0_owserver",
    uuid="e3fa56560d93458b96a594cbcea3017e",
)
_ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("5.6.7.8"),
    ip_addresses=[ip_address("5.6.7.8")],
    hostname="ubuntu.local.",
    name="OWFS (1-wire) Server",
    port=4304,
    type="_owserver._tcp.local.",
    properties={},
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture
async def filled_device_registry(
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> dr.DeviceRegistry:
    """Fill device registry with mock devices."""
    for key in ("28.111111111111", "28.222222222222", "28.222222222223"):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, key)},
            manufacturer=MANUFACTURER_MAXIM,
            model="DS18B20",
            name=key,
        )
    return device_registry


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    new_entry = result["result"]
    assert new_entry.title == "1.2.3.4"
    assert new_entry.data == {CONF_HOST: "1.2.3.4", CONF_PORT: 1234}


async def test_user_flow_recovery(hass: HomeAssistant) -> None:
    """Test user flow recovery after invalid server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Invalid server
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
        side_effect=protocol.ConnError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # Valid server
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    new_entry = result["result"]
    assert new_entry.title == "1.2.3.4"
    assert new_entry.data == {CONF_HOST: "1.2.3.4", CONF_PORT: 1234}


async def test_user_duplicate(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test user duplicate flow."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Duplicate server
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfigure flow."""
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert not result["errors"]

    # Invalid server
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
        side_effect=protocol.ConnError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "2.3.4.5", CONF_PORT: 2345},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    # Valid server
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "2.3.4.5", CONF_PORT: 2345},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_HOST: "2.3.4.5", CONF_PORT: 2345}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_duplicate(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfigure duplicate flow."""
    other_config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_HOST: "2.3.4.5",
            CONF_PORT: 2345,
        },
        entry_id="other",
    )
    other_config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert not result["errors"]

    # Duplicate server
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "2.3.4.5", CONF_PORT: 2345},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert len(mock_setup_entry.mock_calls) == 0
    assert config_entry.data == {CONF_HOST: "1.2.3.4", CONF_PORT: 1234}
    assert other_config_entry.data == {CONF_HOST: "2.3.4.5", CONF_PORT: 2345}


async def test_hassio_flow(hass: HomeAssistant) -> None:
    """Test HassIO discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_HASSIO},
        data=_HASSIO_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert not result["errors"]

    # Cannot connect to server => retry
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
        side_effect=protocol.ConnError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    # Connect OK
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    new_entry = result["result"]
    assert new_entry.title == "owserver (1-wire)"
    assert new_entry.data == {CONF_HOST: "1302b8e0-owserver", CONF_PORT: 4304}


@pytest.mark.usefixtures("config_entry")
async def test_hassio_duplicate(hass: HomeAssistant) -> None:
    """Test HassIO discovery duplicate flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_HASSIO},
        data=_HASSIO_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test zeroconf discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert not result["errors"]

    # Cannot connect to server => retry
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
        side_effect=protocol.ConnError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    # Connect OK
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    new_entry = result["result"]
    assert new_entry.title == "OWFS (1-wire) Server"
    assert new_entry.data == {CONF_HOST: "ubuntu.local.", CONF_PORT: 4304}


@pytest.mark.usefixtures("config_entry")
async def test_zeroconf_duplicate(hass: HomeAssistant) -> None:
    """Test zeroconf discovery duplicate flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("filled_device_registry")
async def test_user_options_clear(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test clearing the options."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Verify that first config step comes back with a selection list of all the 28-family devices
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["data_schema"].schema["device_selection"].options == {
        "28.111111111111": False,
        "28.222222222222": False,
        "28.222222222223": False,
    }

    # Verify that the clear-input action clears the options dict
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={INPUT_ENTRY_CLEAR_OPTIONS: True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}


@pytest.mark.usefixtures("filled_device_registry")
async def test_user_options_empty_selection_recovery(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test leaving the selection of devices empty."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Verify that first config step comes back with a selection list of all the 28-family devices
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["data_schema"].schema["device_selection"].options == {
        "28.111111111111": False,
        "28.222222222222": False,
        "28.222222222223": False,
    }

    # Verify that an empty selection shows the form again
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={INPUT_ENTRY_DEVICE_SELECTION: []},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_selection"
    assert result["errors"] == {"base": "device_not_selected"}

    # Verify that a single selected device to configure comes back as a form with the device to configure
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={INPUT_ENTRY_DEVICE_SELECTION: ["28.111111111111"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["sensor_id"] == "28.111111111111"

    # Verify that the setting for the device comes back as default when no input is given
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"]["device_options"]["28.111111111111"]["precision"]
        == "temperature"
    )


@pytest.mark.usefixtures("filled_device_registry")
async def test_user_options_set_single(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test configuring a single device."""
    # Clear config options to certify functionality when starting from scratch
    hass.config_entries.async_update_entry(config_entry, options={})

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Verify that first config step comes back with a selection list of all the 28-family devices
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["data_schema"].schema["device_selection"].options == {
        "28.111111111111": False,
        "28.222222222222": False,
        "28.222222222223": False,
    }

    # Verify that a single selected device to configure comes back as a form with the device to configure
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={INPUT_ENTRY_DEVICE_SELECTION: ["28.111111111111"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["sensor_id"] == "28.111111111111"

    # Verify that the setting for the device comes back as default when no input is given
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"]["device_options"]["28.111111111111"]["precision"]
        == "temperature"
    )


async def test_user_options_set_multiple(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    filled_device_registry: dr.DeviceRegistry,
) -> None:
    """Test configuring multiple consecutive devices in a row."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Verify that first config step comes back with a selection list of all the 28-family devices
    for entry in dr.async_entries_for_config_entry(
        filled_device_registry, config_entry.entry_id
    ):
        filled_device_registry.async_update_device(entry.id, name_by_user="Given Name")
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["data_schema"].schema["device_selection"].options == {
        "Given Name (28.111111111111)": False,
        "Given Name (28.222222222222)": False,
        "Given Name (28.222222222223)": False,
    }

    # Verify that selecting two devices to configure comes back as a
    #  form with the first device to configure using it's long name as entry
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            INPUT_ENTRY_DEVICE_SELECTION: [
                "Given Name (28.111111111111)",
                "Given Name (28.222222222222)",
            ]
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert (
        result["description_placeholders"]["sensor_id"]
        == "Given Name (28.222222222222)"
    )

    # Verify that next sensor is coming up for configuration after the first
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"precision": "temperature"},
    )
    assert result["type"] is FlowResultType.FORM
    assert (
        result["description_placeholders"]["sensor_id"]
        == "Given Name (28.111111111111)"
    )

    # Verify that the setting for the device comes back as default when no input is given
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"precision": "temperature9"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"]["device_options"]["28.222222222222"]["precision"]
        == "temperature"
    )
    assert (
        result["data"]["device_options"]["28.111111111111"]["precision"]
        == "temperature9"
    )


async def test_user_options_no_devices(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that options does not change when no devices are available."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Verify that first config step comes back with an empty list of possible devices to choose from
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_configurable_devices"
