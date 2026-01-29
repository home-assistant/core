"""Test the Eltako Series 14 config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from serial import SerialException

from homeassistant import config_entries
from homeassistant.components.eltako_series14.const import (
    CONF_FAST_STATUS_CHANGE,
    CONF_GATEWAY_AUTO_RECONNECT,
    CONF_GATEWAY_MESSAGE_DELAY,
    CONF_SENDER_ID,
    CONF_SERIAL_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

_DEFAULT_NAME = "Test Gateway"
_DEFAULT_DATA = {
    CONF_NAME: _DEFAULT_NAME,
    CONF_ID: "00-00-B0-00",
    CONF_MODEL: "FAM14",
    CONF_SERIAL_PORT: "test_port",
    CONF_GATEWAY_AUTO_RECONNECT: True,
    CONF_FAST_STATUS_CHANGE: True,
    CONF_GATEWAY_MESSAGE_DELAY: 0.01,
}


class TestEltakoFlowHandler:
    """Handle the tests for the EltakoFlowHandler."""

    async def test_form(self, hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
        """Test we get the form."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _DEFAULT_DATA
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == _DEFAULT_NAME
        assert result["data"] == _DEFAULT_DATA
        assert len(mock_setup_entry.mock_calls) == 1

    async def test_form_double_abort(
        self, hass: HomeAssistant, mock_setup_entry: AsyncMock
    ) -> None:
        """Test form aborts when setting up the same device."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _DEFAULT_DATA
        )
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _DEFAULT_DATA
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert len(mock_setup_entry.mock_calls) == 1

    async def test_form_no_usb_ports(
        self, hass: HomeAssistant, mock_setup_entry: AsyncMock
    ) -> None:
        """Test we handle missing usb ports."""
        with patch(
            "homeassistant.components.eltako_series14.config_flow.serial.tools.list_ports.comports",
            return_value=[],
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_serial_ports"
        assert len(mock_setup_entry.mock_calls) == 0

    async def test_form_invalid_usb_port(
        self, hass: HomeAssistant, mock_setup_entry: AsyncMock
    ) -> None:
        """Test we handle invalid usb port."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.eltako_series14.config_flow.serial.serial_for_url",
            side_effect=SerialException,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], _DEFAULT_DATA
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_SERIAL_PORT: "invalid_gateway_path"}

        # Check if the form can still be submitted after removing the error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _DEFAULT_DATA
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == _DEFAULT_NAME
        assert result["data"] == _DEFAULT_DATA
        assert len(mock_setup_entry.mock_calls) == 1

    async def test_form_gateway_cannot_connect(
        self, hass: HomeAssistant, mock_setup_entry: AsyncMock
    ) -> None:
        """Test we handle failing gateway connection."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.eltako_series14.config_flow._async_validate_gateway",
            side_effect=RuntimeError,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], _DEFAULT_DATA
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_SERIAL_PORT: "cannot_connect"}

    async def test_form_gateway_unexpected_error(
        self, hass: HomeAssistant, mock_setup_entry: AsyncMock
    ) -> None:
        """Test we handle an unexpected error during gateway connection."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.eltako_series14.config_flow._async_validate_gateway",
            side_effect=Exception,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], _DEFAULT_DATA
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}

    async def test_form_invalid_id(
        self, hass: HomeAssistant, mock_setup_entry: AsyncMock
    ) -> None:
        """Test we handle invalid id format."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Check for small ID
        invalid_data = {**_DEFAULT_DATA, CONF_ID: "00-B0-00-0"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], invalid_data
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_ID: "invalid_id"}

        # Check for ID which is not hex
        invalid_data = {**_DEFAULT_DATA, CONF_ID: "00-G0-00-00"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], invalid_data
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_ID: "invalid_id"}

        # Check if the form can still be submitted after removing the error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _DEFAULT_DATA
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == _DEFAULT_NAME
        assert result["data"] == _DEFAULT_DATA
        assert len(mock_setup_entry.mock_calls) == 1

    async def test_reconfigure_form(
        self, hass: HomeAssistant, mock_setup_entry: AsyncMock
    ) -> None:
        """Test the reconfiguration of an entry."""
        entry = MockConfigEntry(domain=DOMAIN, data=_DEFAULT_DATA)
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**_DEFAULT_DATA, CONF_ID: "00-B1-00-00"},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data[CONF_ID] == "00-B1-00-00"


class TestDeviceSubentryFlowHandler:
    """Handle the tests for the DeviceSubentryFlowHandler."""

    _DEFAULT_SWITCH_NAME = "Default switch"
    _DEFAULT_SWITCH = {
        CONF_NAME: _DEFAULT_SWITCH_NAME,
        CONF_ID: "00-00-00-02",
        CONF_SENDER_ID: "00-00-B0-02",
        CONF_MODEL: "FSR14_2x",
    }

    @pytest.fixture
    def setup_default_entry(self, hass: HomeAssistant) -> MockConfigEntry:
        """Setup a default config entry, that is used by the following test."""
        entry = MockConfigEntry(domain=DOMAIN, data=_DEFAULT_DATA)
        entry.add_to_hass(hass)
        return entry

    async def test_subentry_switch(
        self, hass: HomeAssistant, setup_default_entry: MockConfigEntry
    ):
        """Test setting up a switch device."""
        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={"next_step_id": "switch"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "switch"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input=self._DEFAULT_SWITCH
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == self._DEFAULT_SWITCH_NAME
        assert result["data"] == self._DEFAULT_SWITCH

    async def test_subentry_already_configured(
        self, hass: HomeAssistant, setup_default_entry: MockConfigEntry
    ):
        """Test if no dupliucates are created."""
        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={"next_step_id": "switch"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input=self._DEFAULT_SWITCH
        )
        await hass.async_block_till_done()

        # Trying to create a duplicate
        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={"next_step_id": "switch"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input=self._DEFAULT_SWITCH
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_ID: "already_configured"}

        # Trying to create a new entry after duplicate was detected
        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={"next_step_id": "switch"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**self._DEFAULT_SWITCH, CONF_ID: "00-00-00-03"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == self._DEFAULT_SWITCH_NAME
        assert result["data"] == {**self._DEFAULT_SWITCH, CONF_ID: "00-00-00-03"}

    async def test_subentry_invalid_id(
        self, hass: HomeAssistant, setup_default_entry: MockConfigEntry
    ):
        """Test if an invalid id format is handled correctly."""
        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={"next_step_id": "switch"}
        )

        # Check for small ID
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**self._DEFAULT_SWITCH, CONF_ID: "00-B0-00-0"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_ID: "invalid_id"}

        # Check for ID which is not hex
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**self._DEFAULT_SWITCH, CONF_SENDER_ID: "00-G0-00-00"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_SENDER_ID: "invalid_id"}

        # Check if the form can still be submitted after removing the error
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input=self._DEFAULT_SWITCH
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == self._DEFAULT_SWITCH_NAME
        assert result["data"] == self._DEFAULT_SWITCH

    async def test_reconfigure_subentry(
        self, hass: HomeAssistant, setup_default_entry: MockConfigEntry
    ) -> None:
        """Test the reconfiguration of an subentry."""

        # Create a subentry
        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={"next_step_id": "switch"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input=self._DEFAULT_SWITCH
        )
        await hass.async_block_till_done()

        subentry = next(iter(setup_default_entry.subentries.values()))

        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": setup_default_entry.entry_id,
                "subentry_id": subentry.subentry_id,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "switch"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**self._DEFAULT_SWITCH, CONF_ID: "00-00-00-03"},
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert subentry.data[CONF_ID] == "00-00-00-03"

    async def test_reconfigure_subentry_model_not_found(
        self, hass: HomeAssistant, setup_default_entry: MockConfigEntry
    ) -> None:
        """Test when the model is not found during the reconfiguration of an subentry."""

        # Create a subentry
        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={"next_step_id": "switch"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input=self._DEFAULT_SWITCH
        )
        await hass.async_block_till_done()

        subentry = next(iter(setup_default_entry.subentries.values()))

        with patch(
            "homeassistant.components.eltako_series14.config_flow.SWITCH_MODELS",
            return_value={},
        ):
            result = await hass.config_entries.subentries.async_init(
                (setup_default_entry.entry_id, "device"),
                context={
                    "source": config_entries.SOURCE_RECONFIGURE,
                    "entry_id": setup_default_entry.entry_id,
                    "subentry_id": subentry.subentry_id,
                },
            )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "model_not_found"
