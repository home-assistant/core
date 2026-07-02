"""Test the Panasonic Viera config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from panasonic_viera import SOAPError
import pytest

from homeassistant import config_entries
from homeassistant.components.panasonic_viera.const import (
    ATTR_DEVICE_INFO,
    ATTR_UDN,
    CONF_ON_ACTION,
    DEFAULT_NAME,
    DOMAIN,
    ERROR_INVALID_PIN_CODE,
)
from homeassistant.const import CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_BASIC_DATA,
    MOCK_CONFIG_DATA,
    MOCK_DEVICE_INFO,
    MOCK_ENCRYPTION_DATA,
    MOCK_TURN_ON_ACTION,
    get_mock_remote,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.panasonic_viera.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


async def test_flow_non_encrypted(hass: HomeAssistant) -> None:
    """Test flow without encryption."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=False)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_BASIC_DATA},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {**MOCK_CONFIG_DATA, ATTR_DEVICE_INFO: MOCK_DEVICE_INFO}


async def test_flow_not_connected_error(hass: HomeAssistant) -> None:
    """Test flow with connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_BASIC_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_unknown_abort(hass: HomeAssistant) -> None:
    """Test flow with unknown error abortion."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_BASIC_DATA},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_flow_encrypted_not_connected_pin_code_request(
    hass: HomeAssistant,
) -> None:
    """Test encrypted flow with PIN request connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, request_error=TimeoutError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_BASIC_DATA},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_flow_encrypted_unknown_pin_code_request(hass: HomeAssistant) -> None:
    """Test encrypted flow with PIN request unknown error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, request_error=Exception)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_BASIC_DATA},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_flow_encrypted_valid_pin_code(hass: HomeAssistant) -> None:
    """Test flow with encryption and valid PIN code."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(
        encrypted=True,
        app_id="mock-app-id",
        encryption_key="mock-encryption-key",
    )

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_BASIC_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        **MOCK_CONFIG_DATA,
        **MOCK_ENCRYPTION_DATA,
        ATTR_DEVICE_INFO: MOCK_DEVICE_INFO,
    }


async def test_flow_encrypted_invalid_pin_code_error(hass: HomeAssistant) -> None:
    """Test flow with encryption and invalid PIN code error during pairing step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, authorize_error=SOAPError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_BASIC_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "0000"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"
    assert result["errors"] == {"base": ERROR_INVALID_PIN_CODE}


async def test_flow_encrypted_not_connected_abort(hass: HomeAssistant) -> None:
    """Test encrypted flow with PIN connection error during pairing."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, authorize_error=TimeoutError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_BASIC_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "0000"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_flow_encrypted_unknown_abort(hass: HomeAssistant) -> None:
    """Test encrypted flow with PIN unknown error during pairing."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, authorize_error=Exception)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_BASIC_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "0000"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_flow_non_encrypted_already_configured_abort(hass: HomeAssistant) -> None:
    """Test flow without encryption and existing config entry abortion."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0.0.0.0",
        data=MOCK_CONFIG_DATA,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={**MOCK_BASIC_DATA},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_encrypted_already_configured_abort(hass: HomeAssistant) -> None:
    """Test flow with encryption and existing config entry abortion."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0.0.0.0",
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={**MOCK_BASIC_DATA},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_imported_flow_non_encrypted(hass: HomeAssistant) -> None:
    """Test imported flow without encryption."""

    mock_remote = get_mock_remote(encrypted=False)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={**MOCK_CONFIG_DATA},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {**MOCK_CONFIG_DATA, ATTR_DEVICE_INFO: MOCK_DEVICE_INFO}


async def test_imported_flow_encrypted_valid_pin_code(hass: HomeAssistant) -> None:
    """Test imported flow with encryption and valid PIN code."""

    mock_remote = get_mock_remote(
        encrypted=True,
        app_id="mock-app-id",
        encryption_key="mock-encryption-key",
    )

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={**MOCK_CONFIG_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        **MOCK_CONFIG_DATA,
        **MOCK_ENCRYPTION_DATA,
        ATTR_DEVICE_INFO: MOCK_DEVICE_INFO,
    }


async def test_imported_flow_encrypted_invalid_pin_code_error(
    hass: HomeAssistant,
) -> None:
    """Test imported encrypted flow with invalid PIN error."""

    mock_remote = get_mock_remote(encrypted=True, authorize_error=SOAPError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={**MOCK_CONFIG_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "0000"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"
    assert result["errors"] == {"base": ERROR_INVALID_PIN_CODE}


async def test_imported_flow_encrypted_not_connected_abort(hass: HomeAssistant) -> None:
    """Test imported encrypted flow with PIN connection error."""

    mock_remote = get_mock_remote(encrypted=True, authorize_error=TimeoutError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={**MOCK_CONFIG_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "0000"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_imported_flow_encrypted_unknown_abort(hass: HomeAssistant) -> None:
    """Test imported encrypted flow with PIN unknown error."""

    mock_remote = get_mock_remote(encrypted=True, authorize_error=Exception)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={**MOCK_CONFIG_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "0000"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_imported_flow_not_connected_error(hass: HomeAssistant) -> None:
    """Test imported flow with connection error abortion."""

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={**MOCK_CONFIG_DATA},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_imported_flow_unknown_abort(hass: HomeAssistant) -> None:
    """Test imported flow with unknown error abortion."""

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={**MOCK_CONFIG_DATA},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_imported_flow_non_encrypted_already_configured_abort(
    hass: HomeAssistant,
) -> None:
    """Test imported flow without encryption and existing config entry abortion."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0.0.0.0",
        data=MOCK_CONFIG_DATA,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={**MOCK_BASIC_DATA},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_imported_flow_encrypted_already_configured_abort(
    hass: HomeAssistant,
) -> None:
    """Test imported flow with encryption and existing config entry abortion."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0.0.0.0",
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={**MOCK_BASIC_DATA},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test setting turn_on_action through the options flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={
            **MOCK_CONFIG_DATA,
            **MOCK_ENCRYPTION_DATA,
            ATTR_DEVICE_INFO: MOCK_DEVICE_INFO,
        },
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ON_ACTION: MOCK_TURN_ON_ACTION},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options == {CONF_ON_ACTION: MOCK_TURN_ON_ACTION}


async def test_options_flow_prefills_legacy_yaml_action(hass: HomeAssistant) -> None:
    """Test that the options flow exposes a legacy YAML-imported action.

    Entries originally imported from configuration.yaml store turn_on_action in
    ``data``. The options flow must read the existing value so the user can edit
    it instead of losing it on first save.
    """
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={
            **MOCK_CONFIG_DATA,
            CONF_ON_ACTION: MOCK_TURN_ON_ACTION,
            ATTR_DEVICE_INFO: MOCK_DEVICE_INFO,
        },
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    schema = result["data_schema"].schema
    on_action_marker = next(key for key in schema if key.schema == CONF_ON_ACTION)
    assert on_action_marker.default() == MOCK_TURN_ON_ACTION
