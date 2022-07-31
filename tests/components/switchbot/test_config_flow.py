"""Test the switchbot config flow."""

from unittest.mock import patch

from homeassistant.components.switchbot.const import CONF_RETRY_COUNT
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE
from homeassistant.data_entry_flow import FlowResultType

from . import (
    NOT_SWITCHBOT_INFO,
    USER_INPUT,
    USER_INPUT_CURTAIN,
    USER_INPUT_SENSOR,
    WOCURTAIN_SERVICE_INFO,
    WOHAND_SERVICE_INFO,
    WOSENSORTH_SERVICE_INFO,
    init_integration,
    patch_async_setup_entry,
)

from tests.common import MockConfigEntry

DOMAIN = "switchbot"


async def test_bluetooth_discovery(hass):
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOHAND_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_NAME: "test-name",
        CONF_PASSWORD: "test-password",
        CONF_SENSOR_TYPE: "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_already_setup(hass):
    """Test discovery via bluetooth with a valid device when already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "bot",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOHAND_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_not_switchbot(hass):
    """Test discovery via bluetooth not switchbot."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=NOT_SWITCHBOT_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_user_setup_wohand(hass):
    """Test the user initiated form with password and valid mac."""

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOHAND_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_NAME: "test-name",
        CONF_PASSWORD: "test-password",
        CONF_SENSOR_TYPE: "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_setup_wohand_already_configured(hass):
    """Test the user initiated form with password and valid mac."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "bot",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOHAND_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_unconfigured_devices"


async def test_user_setup_wocurtain(hass):
    """Test the user initiated form with password and valid mac."""

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOCURTAIN_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT_CURTAIN,
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_NAME: "test-name",
        CONF_PASSWORD: "test-password",
        CONF_SENSOR_TYPE: "curtain",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_setup_wosensor(hass):
    """Test the user initiated form with password and valid mac."""
    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOSENSORTH_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT_SENSOR,
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_NAME: "test-name",
        CONF_PASSWORD: "test-password",
        CONF_SENSOR_TYPE: "hygrometer",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_no_devices(hass):
    """Test the user initiated form with password and valid mac."""
    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_unconfigured_devices"


async def test_async_step_user_takes_precedence_over_discovery(hass):
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOCURTAIN_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOCURTAIN_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] == FlowResultType.FORM

    with patch_async_setup_entry() as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-name"
    assert result2["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_NAME: "test-name",
        CONF_PASSWORD: "test-password",
        CONF_SENSOR_TYPE: "curtain",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    # Verify the original one was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def test_options_flow(hass):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "bot",
        },
        options={
            CONF_RETRY_COUNT: 10,
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_RETRY_COUNT: 3,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RETRY_COUNT] == 3

    assert len(mock_setup_entry.mock_calls) == 2

    # Test changing of entry options.

    with patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_RETRY_COUNT: 6,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RETRY_COUNT] == 6

    assert len(mock_setup_entry.mock_calls) == 1

    assert entry.options[CONF_RETRY_COUNT] == 6
