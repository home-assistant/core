"""Test the Avea config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.avea.config_flow import CannotConnect, _validate_device
from homeassistant.components.avea.const import DOMAIN
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_IMPORT
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import AVEA_DISCOVERY_INFO, NOT_AVEA_DISCOVERY_INFO

from tests.common import MockConfigEntry


def test_validate_device_falls_back_to_discovery_name() -> None:
    """Test the validator falls back when obtaining the name fails."""
    bulb = MagicMock()
    bulb.connect.return_value = True
    bulb.get_name.side_effect = RuntimeError
    bulb.get_brightness.return_value = 0

    with patch(
        "homeassistant.components.avea.config_flow.avea.Bulb", return_value=bulb
    ):
        assert _validate_device(AVEA_DISCOVERY_INFO) == AVEA_DISCOVERY_INFO.name


def test_validate_device_raises_cannot_connect_on_brightness_error() -> None:
    """Test the validator maps brightness errors to cannot connect."""
    bulb = MagicMock()
    bulb.connect.return_value = True
    bulb.get_name.return_value = "Bedroom"
    bulb.get_brightness.side_effect = RuntimeError

    with (
        patch("homeassistant.components.avea.config_flow.avea.Bulb", return_value=bulb),
        pytest.raises(CannotConnect),
    ):
        _validate_device(AVEA_DISCOVERY_INFO)


def test_validate_device_raises_cannot_connect_on_none_brightness() -> None:
    """Test the validator treats None brightness as cannot connect."""
    bulb = MagicMock()
    bulb.connect.return_value = True
    bulb.get_name.return_value = "Bedroom"
    bulb.get_brightness.return_value = None

    with (
        patch("homeassistant.components.avea.config_flow.avea.Bulb", return_value=bulb),
        pytest.raises(CannotConnect),
    ):
        _validate_device(AVEA_DISCOVERY_INFO)


def test_validate_device_raises_cannot_connect_on_connect_error() -> None:
    """Test the validator maps connect errors to cannot connect."""
    bulb = MagicMock()
    bulb.connect.side_effect = RuntimeError

    with (
        patch("homeassistant.components.avea.config_flow.avea.Bulb", return_value=bulb),
        pytest.raises(CannotConnect),
    ):
        _validate_device(AVEA_DISCOVERY_INFO)


def test_validate_device_raises_cannot_connect_on_close_error() -> None:
    """Test the validator maps close errors to cannot connect."""
    bulb = MagicMock()
    bulb.connect.return_value = True
    bulb.get_name.return_value = "Bedroom"
    bulb.get_brightness.return_value = 0
    bulb.close.side_effect = RuntimeError

    with (
        patch("homeassistant.components.avea.config_flow.avea.Bulb", return_value=bulb),
        pytest.raises(CannotConnect),
    ):
        _validate_device(AVEA_DISCOVERY_INFO)


def test_validate_device_preserves_cannot_connect_when_close_raises() -> None:
    """Test cleanup errors do not mask an existing cannot connect error."""
    bulb = MagicMock()
    bulb.connect.return_value = False
    bulb.close.side_effect = RuntimeError

    with (
        patch("homeassistant.components.avea.config_flow.avea.Bulb", return_value=bulb),
        pytest.raises(CannotConnect),
    ):
        _validate_device(AVEA_DISCOVERY_INFO)


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test the user step success path."""
    with patch(
        "homeassistant.components.avea.config_flow.async_discovered_service_info",
        return_value=[NOT_AVEA_DISCOVERY_INFO, AVEA_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.avea.config_flow._validate_device",
            return_value="Living Room",
        ),
        patch("homeassistant.components.avea.async_setup_entry", return_value=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Living Room"
    assert result2["data"] == {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address}
    assert result2["result"].unique_id == AVEA_DISCOVERY_INFO.address


async def test_user_step_no_devices_found(hass: HomeAssistant) -> None:
    """Test the user step when no devices are found."""
    with patch(
        "homeassistant.components.avea.config_flow.async_discovered_service_info",
        return_value=[NOT_AVEA_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test the user step when the device cannot be connected to."""
    with patch(
        "homeassistant.components.avea.config_flow.async_discovered_service_info",
        return_value=[AVEA_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.avea.config_flow._validate_device",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_step_unknown_error(hass: HomeAssistant) -> None:
    """Test the user step when an unknown error occurs."""
    with patch(
        "homeassistant.components.avea.config_flow.async_discovered_service_info",
        return_value=[AVEA_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.avea.config_flow._validate_device",
        side_effect=RuntimeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


async def test_bluetooth_step_success(hass: HomeAssistant) -> None:
    """Test the bluetooth discovery step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=AVEA_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.avea.config_flow._validate_device",
            return_value="Avea Bulb",
        ),
        patch("homeassistant.components.avea.async_setup_entry", return_value=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Avea Bulb"
    assert result2["data"] == {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address}
    assert result2["result"].unique_id == AVEA_DISCOVERY_INFO.address


async def test_import_step_success(hass: HomeAssistant) -> None:
    """Test the YAML import step."""
    with patch("homeassistant.components.avea.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_ADDRESS: AVEA_DISCOVERY_INFO.address,
                CONF_NAME: "Bedroom",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom"
    assert result["data"] == {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address}
    assert result["result"].unique_id == AVEA_DISCOVERY_INFO.address


async def test_user_step_replaces_ignored_device(hass: HomeAssistant) -> None:
    """Test the user flow can replace an ignored device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=AVEA_DISCOVERY_INFO.address,
        source=SOURCE_IGNORE,
        data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.avea.config_flow.async_discovered_service_info",
        return_value=[AVEA_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert (
        AVEA_DISCOVERY_INFO.address
        in result["data_schema"].schema[CONF_ADDRESS].container
    )

    with (
        patch(
            "homeassistant.components.avea.config_flow._validate_device",
            return_value="Bedroom",
        ),
        patch("homeassistant.components.avea.async_setup_entry", return_value=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Bedroom"
    assert result2["data"] == {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address}
    assert result2["result"].unique_id == AVEA_DISCOVERY_INFO.address
