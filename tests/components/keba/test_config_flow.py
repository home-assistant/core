"""Test the KEBA charging station config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.keba.const import (
    CONF_FS,
    CONF_FS_FALLBACK,
    CONF_FS_PERSIST,
    CONF_FS_TIMEOUT,
    CONF_RFID,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_RFID: "",
    CONF_FS: False,
    CONF_FS_TIMEOUT: 30,
    CONF_FS_FALLBACK: 6,
    CONF_FS_PERSIST: 0,
}


def _mock_keba_handler(serial: str = "12345678", product: str = "KC-P30"):
    """Return a mock KebaHandler that connects successfully."""
    mock = AsyncMock()
    mock.setup.return_value = True
    mock.get_value = MagicMock(side_effect={"Serial": serial, "Product": product}.get)
    mock.device_name = product
    mock.device_id = f"keba_wallbox_{serial}"
    return mock


async def test_form_shows_on_init(hass: HomeAssistant) -> None:
    """Test that the user step form is shown on init."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_successful_setup(hass: HomeAssistant) -> None:
    """Test a successful config entry creation."""
    with (
        patch(
            "homeassistant.components.keba.config_flow.KebaHandler",
            return_value=_mock_keba_handler(),
        ),
        patch(
            "homeassistant.components.keba.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "KC-P30"
    assert result2["data"] == USER_INPUT


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test that cannot_connect error is shown when setup returns False."""
    mock = _mock_keba_handler()
    mock.setup.return_value = False

    with patch(
        "homeassistant.components.keba.config_flow.KebaHandler",
        return_value=mock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_unknown_exception(hass: HomeAssistant) -> None:
    """Test that unknown error is shown when an exception is raised."""
    mock = _mock_keba_handler()
    mock.setup.side_effect = Exception("Unexpected error")

    with patch(
        "homeassistant.components.keba.config_flow.KebaHandler",
        return_value=mock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_import_from_yaml(hass: HomeAssistant) -> None:
    """Test that a YAML config is silently imported as a config entry."""
    with (
        patch(
            "homeassistant.components.keba.config_flow.KebaHandler",
            return_value=_mock_keba_handler(),
        ),
        patch(
            "homeassistant.components.keba.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "KC-P30"
    assert result["data"] == USER_INPUT


async def test_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test that a failed import aborts with cannot_connect."""
    mock = _mock_keba_handler()
    mock.setup.return_value = False

    with patch(
        "homeassistant.components.keba.config_flow.KebaHandler",
        return_value=mock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_exception(hass: HomeAssistant) -> None:
    """Test that an exception during import aborts with cannot_connect."""
    mock = _mock_keba_handler()
    mock.setup.side_effect = Exception("unexpected error")

    with patch(
        "homeassistant.components.keba.config_flow.KebaHandler",
        return_value=mock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_reconfigure_shows_form(hass: HomeAssistant) -> None:
    """Test that the reconfigure step shows the form."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id="12345678")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_updates_entry(hass: HomeAssistant) -> None:
    """Test that submitting reconfigure updates the entry data."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id="12345678")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    new_data = {**USER_INPUT, "failsafe_timeout": 60}
    with patch(
        "homeassistant.components.keba.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_data
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that a second setup is blocked because single_config_entry is true."""
    with (
        patch(
            "homeassistant.components.keba.config_flow.KebaHandler",
            return_value=_mock_keba_handler(),
        ),
        patch(
            "homeassistant.components.keba.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
