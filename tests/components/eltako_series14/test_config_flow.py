"""Test the Eltako Series 14 config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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
from homeassistant.config_entries import SubentryFlowResult
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


@pytest.fixture(autouse=True)
def mock_serial_ports():
    """Override serial.tools.list_ports.comports."""
    mock_port = MagicMock()
    mock_port.device = "test_port"
    mock_port.description = "Test Serial Port"
    with patch(
        "homeassistant.components.eltako_series14.config_flow.serial.tools.list_ports.comports",
        return_value=[mock_port],
    ):
        yield


@pytest.fixture(autouse=True)
def mock_serial_for_url() -> Generator[Mock]:
    """Override serial.serial_for_url."""
    with patch(
        "homeassistant.components.eltako_series14.config_flow.serial.serial_for_url",
        return_value=True,
    ) as mock_serial_for_url:
        yield mock_serial_for_url


@pytest.fixture(autouse=True)
def mock_gateway() -> Generator[AsyncMock]:
    """Override EltakoGateway."""
    with patch(
        "homeassistant.components.eltako_series14.config_flow.EltakoGateway",
        autospec=True,
    ) as mock_gateway:
        yield mock_gateway


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
        mock_setup_entry.assert_called_once()

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
        mock_setup_entry.assert_called_once()

    @pytest.mark.parametrize(
        ("return_value", "side_effect", "expected_reason"),
        [
            ([], None, "no_serial_ports"),
            (..., OSError, "cannot_list_serial_ports"),
        ],
    )
    async def test_form_serial_port_errors(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
        return_value: list | None,
        side_effect: Exception | None,
        expected_reason: str,
    ) -> None:
        """Test we handle missing usb ports."""
        with patch(
            "homeassistant.components.eltako_series14.config_flow.serial.tools.list_ports.comports",
            return_value=return_value,
            side_effect=side_effect,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == expected_reason
        mock_setup_entry.assert_not_called()

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
        mock_setup_entry.assert_called_once()

    @pytest.mark.parametrize(
        ("exception", "expected_errors"),
        [
            (RuntimeError, {CONF_SERIAL_PORT: "cannot_connect"}),
            (Exception, {"base": "unknown"}),
        ],
    )
    async def test_form_gateway_validation_errors(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
        exception: Exception,
        expected_errors: dict[str, str],
    ) -> None:
        """Test we handle failing gateway connection."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.eltako_series14.config_flow.EltakoFlowHandler._async_validate_gateway",
            side_effect=exception,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], _DEFAULT_DATA
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == expected_errors
        mock_setup_entry.assert_not_called()

    @pytest.mark.parametrize("invalid_id", ["00-B0-00-0", "00-G0-00-00"])
    async def test_form_invalid_id(
        self, hass: HomeAssistant, mock_setup_entry: AsyncMock, invalid_id: str
    ) -> None:
        """Test we handle invalid id format."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        invalid_data = {**_DEFAULT_DATA, CONF_ID: invalid_id}
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
        mock_setup_entry.assert_called_once()

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
        mock_setup_entry.assert_called_once()

    async def test_reconfigure_error(
        self, hass: HomeAssistant, mock_setup_entry: AsyncMock
    ) -> None:
        """Test error handling and recovering during reconfiguration."""
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

        # Check for small ID
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**_DEFAULT_DATA, CONF_ID: "00-B0-00-0"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_ID: "invalid_id"}

        # Check for ID which is not hex
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**_DEFAULT_DATA, CONF_ID: "00-B1-00-00"},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data[CONF_ID] == "00-B1-00-00"
        mock_setup_entry.assert_called_once()


class TestDeviceSubentryFlowHandler:
    """Handle the tests for the DeviceSubentryFlowHandler."""

    _DEFAULT_SWITCH_NAME = "Default switch"
    _DEFAULT_SWITCH = {
        CONF_NAME: _DEFAULT_SWITCH_NAME,
        CONF_ID: "00-00-00-02",
        CONF_SENDER_ID: "00-00-B0-02",
        CONF_MODEL: "FSR14_2x",
    }

    async def _create_default_subentry(
        self, hass: HomeAssistant, entry_id: str
    ) -> SubentryFlowResult:
        """Helper to navigate the flow and create a subentry."""
        result = await hass.config_entries.subentries.async_init(
            (entry_id, "device"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={"next_step_id": "switch"}
        )
        return await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input=self._DEFAULT_SWITCH
        )

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
        """Test if no duplicates are created."""
        result = await self._create_default_subentry(hass, setup_default_entry.entry_id)
        await hass.async_block_till_done()

        # Trying to create a duplicate
        result = await self._create_default_subentry(hass, setup_default_entry.entry_id)
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

    @pytest.mark.parametrize("invalid_id", ["00-B0-00-0", "00-G0-00-00"])
    async def test_subentry_invalid_id(
        self, hass: HomeAssistant, setup_default_entry: MockConfigEntry, invalid_id: str
    ):
        """Test if an invalid id format is handled correctly."""
        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={"next_step_id": "switch"}
        )

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**self._DEFAULT_SWITCH, CONF_ID: invalid_id},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_ID: "invalid_id"}

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**self._DEFAULT_SWITCH, CONF_SENDER_ID: invalid_id},
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

        result = await self._create_default_subentry(hass, setup_default_entry.entry_id)
        await hass.async_block_till_done()

        # Reconfigure the subentry
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

    async def test_reconfigure_subentry_error(
        self, hass: HomeAssistant, setup_default_entry: MockConfigEntry
    ) -> None:
        """Test error handling and recovering during the reconfiguration of a subentry."""

        result = await self._create_default_subentry(hass, setup_default_entry.entry_id)
        await hass.async_block_till_done()

        # Reconfigure with invalid ID
        subentry = next(iter(setup_default_entry.subentries.values()))
        result = await hass.config_entries.subentries.async_init(
            (setup_default_entry.entry_id, "device"),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": setup_default_entry.entry_id,
                "subentry_id": subentry.subentry_id,
            },
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**self._DEFAULT_SWITCH, CONF_ID: "00-00-00-0"},
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_ID: "invalid_id"}

        # Reconfigure with valid ID
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

        result = await self._create_default_subentry(hass, setup_default_entry.entry_id)
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
