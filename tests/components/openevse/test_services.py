"""Tests for OpenEVSE services."""

from unittest.mock import MagicMock

from aiohttp import ContentTypeError, ServerTimeoutError
from openevsehttp.exceptions import (
    AuthenticationError,
    ParseJSONError,
    UnknownError,
    UnsupportedFeature,
)
import pytest

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

SERVICE_SET_OVERRIDE = "set_override"
SERVICE_CLEAR_OVERRIDE = "clear_override"
SERVICE_GET_OVERRIDE = "get_override"


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Set up OpenEVSE integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def device_entry(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    setup_integration: None,
) -> dr.DeviceEntry:
    """Get the OpenEVSE device entry."""
    identifier = mock_config_entry.unique_id or mock_config_entry.entry_id
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, identifier), mock_config_entry.entry_id
    )
    assert device is not None
    return device


async def test_set_override_minimal(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test calling set_override with only device_id."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_OVERRIDE,
        {ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )

    mock_charger.set_override.assert_called_once_with(
        state=None,
        charge_current=None,
        max_current=None,
        energy_limit=None,
        time_limit=None,
        auto_release=None,
    )


async def test_set_override_all_fields(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test calling set_override with all valid fields."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_OVERRIDE,
        {
            ATTR_DEVICE_ID: device_entry.id,
            "state": "active",
            "charge_current": 32,
            "max_current": 48,
            "energy_limit": 15000,
            "time_limit": {"hours": 1, "minutes": 30},
            "auto_release": True,
        },
        blocking=True,
    )

    mock_charger.set_override.assert_called_once_with(
        state="active",
        charge_current=32,
        max_current=48,
        energy_limit=15000,
        time_limit=5400,
        auto_release=True,
    )


async def test_clear_override(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test calling clear_override."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_OVERRIDE,
        {ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )

    mock_charger.clear_override.assert_called_once()


async def test_get_override(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test calling get_override."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_OVERRIDE,
        {ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
        return_response=True,
    )

    mock_charger.get_override.assert_called_once()
    assert response == {
        "state": "active",
        "charge_current": 32,
        "max_current": 48,
        "energy_limit": 10000,
        "time_limit": 3600,
        "auto_release": True,
    }


async def test_get_override_non_dict_response(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test calling get_override when charger returns non-dict."""
    mock_charger.get_override.return_value = ["item1", "item2"]

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_OVERRIDE,
        {ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
        return_response=True,
    )

    assert response == {"override": ["item1", "item2"]}


async def test_set_override_with_entity_id(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test calling set_override with entity_id target."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_OVERRIDE,
        {
            ATTR_ENTITY_ID: "switch.openevse_mock_config_manual_override",
            "state": "active",
            "charge_current": 32,
        },
        blocking=True,
    )

    mock_charger.set_override.assert_called_once_with(
        state="active",
        charge_current=32,
        max_current=None,
        energy_limit=None,
        time_limit=None,
        auto_release=None,
    )


async def test_clear_override_with_entity_id(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test calling clear_override with entity_id target."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_OVERRIDE,
        {ATTR_ENTITY_ID: "switch.openevse_mock_config_manual_override"},
        blocking=True,
    )

    mock_charger.clear_override.assert_called_once()


async def test_get_override_with_entity_id(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    device_entry: dr.DeviceEntry,
) -> None:
    """Test calling get_override with entity_id target."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_OVERRIDE,
        {ATTR_ENTITY_ID: "switch.openevse_mock_config_manual_override"},
        blocking=True,
        return_response=True,
    )

    mock_charger.get_override.assert_called_once()
    assert response == {
        "state": "active",
        "charge_current": 32,
        "max_current": 48,
        "energy_limit": 10000,
        "time_limit": 3600,
        "auto_release": True,
    }


async def test_service_unknown_device(
    hass: HomeAssistant,
    setup_integration: None,
) -> None:
    """Test service call with non-existent device."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_OVERRIDE,
            {ATTR_DEVICE_ID: "unknown_device_id"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_matching_target_entries"


async def test_service_unknown_entity(
    hass: HomeAssistant,
    setup_integration: None,
) -> None:
    """Test service call with non-existent entity."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_OVERRIDE,
            {ATTR_ENTITY_ID: "switch.non_existent"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_matching_target_entries"


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        pytest.param(
            ValueError("invalid value"), ServiceValidationError, id="value_error"
        ),
        pytest.param(
            AuthenticationError("auth failed"), ConfigEntryAuthFailed, id="auth_error"
        ),
        pytest.param(TimeoutError("timeout"), HomeAssistantError, id="timeout_error"),
        pytest.param(
            ServerTimeoutError("server timeout"),
            HomeAssistantError,
            id="server_timeout",
        ),
        pytest.param(
            ParseJSONError("json error"), HomeAssistantError, id="parse_json_error"
        ),
        pytest.param(
            UnsupportedFeature("old fw"), HomeAssistantError, id="unsupported_feature"
        ),
        pytest.param(
            ContentTypeError(MagicMock(), (), message="bad content"),
            HomeAssistantError,
            id="content_type_error",
        ),
        pytest.param(UnknownError("unknown"), HomeAssistantError, id="unknown_error"),
        pytest.param(RuntimeError("runtime"), HomeAssistantError, id="runtime_error"),
    ],
)
async def test_service_exceptions(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    device_entry: dr.DeviceEntry,
    raised: Exception,
    expected: type[Exception],
) -> None:
    """Test exception handling in override services."""
    mock_charger.set_override.side_effect = raised

    with pytest.raises(expected):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_OVERRIDE,
            {ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
        )
