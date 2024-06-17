"""Test the Hue BLE config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

from homeassistant import config_entries
from homeassistant.components.hue_ble.config_flow import (
    CannotConnect,
    InvalidAuth,
    NotFound,
    ScannerNotAvailable,
)
from homeassistant.components.hue_ble.const import DOMAIN
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import HUE_BLE_SERVICE_INFO, TEST_DEVICE_MAC, TEST_DEVICE_NAME

from tests.components.bluetooth import generate_ble_device


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test form with good data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.authenticated",
            return_value=True,
            new_callable=PropertyMock,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connected",
            return_value=True,
            new_callable=PropertyMock,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.poll_state",
            return_value=(True, []),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_scanners(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test form when no scanners available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.async_scanner_count",
            return_value=0,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_scanners"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_device_not_found(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test form when device not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.async_scanner_count",
            return_value=1,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "not_found"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_not_authenticated(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test form when not authenticated to device (pair failed)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=generate_ble_device(TEST_DEVICE_MAC, TEST_DEVICE_NAME),
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.authenticated",
            return_value=False,
            new_callable=PropertyMock,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test form when device connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=generate_ble_device(TEST_DEVICE_MAC, TEST_DEVICE_NAME),
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.authenticated",
            return_value=True,
            new_callable=PropertyMock,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connected",
            return_value=False,
            new_callable=PropertyMock,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_failed_poll(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test form when polling data & metadata fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=generate_ble_device(TEST_DEVICE_MAC, TEST_DEVICE_NAME),
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.authenticated",
            return_value=True,
            new_callable=PropertyMock,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connected",
            return_value=True,
            new_callable=PropertyMock,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.poll_state",
            return_value=(True, ["Error :P"]),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test form when unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test bluetooth discovery form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_form_no_scanners(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth discovery form when no scanners available."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=ScannerNotAvailable,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_scanners"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_form_device_not_found(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth discovery form when device not found."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=NotFound,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "not_found"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_form_not_authenticated(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth discovery form when not authenticated to device (pair failed)."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth discovery form when connection to device fails."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_form_unknown(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth discovery form when unknown error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
    }

    assert len(mock_setup_entry.mock_calls) == 1
