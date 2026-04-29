"""Tests for the Peblar select platform."""

from unittest.mock import MagicMock

from peblar import (
    LedBrightness,
    PeblarAuthenticationError,
    PeblarConnectionError,
    PeblarError,
    SmartChargingMode,
    SoundVolume,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = [
    pytest.mark.parametrize("init_integration", [Platform.SELECT], indirect=True),
    pytest.mark.usefixtures("init_integration"),
]


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the select entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure all entities are correctly assigned to the Peblar EV charger
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "23-45-A4O-MOF")}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_option(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
    """Test the Peblar EV charger selects."""
    entity_id = "select.peblar_ev_charger_smart_charging"
    mocked_method = mock_peblar.smart_charging
    mocked_method.reset_mock()

    # Test normal happy path for changing the select option
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "default",
        },
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 1
    mocked_method.assert_called_with(SmartChargingMode.DEFAULT)


@pytest.mark.parametrize(
    ("error", "error_match", "translation_key", "translation_placeholders"),
    [
        (
            PeblarConnectionError("Could not connect"),
            (
                r"An error occurred while communicating "
                r"with the Peblar EV charger: Could not connect"
            ),
            "communication_error",
            {"error": "Could not connect"},
        ),
        (
            PeblarError("Unknown error"),
            (
                r"An unknown error occurred while communicating "
                r"with the Peblar EV charger: Unknown error"
            ),
            "unknown_error",
            {"error": "Unknown error"},
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_option_communication_error(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    error_match: str,
    translation_key: str,
    translation_placeholders: dict,
) -> None:
    """Test the Peblar EV charger when a communication error occurs."""
    entity_id = "select.peblar_ev_charger_smart_charging"
    mock_peblar.smart_charging.side_effect = error

    with pytest.raises(
        HomeAssistantError,
        match=error_match,
    ) as excinfo:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: "default",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == translation_key
    assert excinfo.value.translation_placeholders == translation_placeholders


async def test_select_option_authentication_error(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Peblar EV charger when an authentication error occurs."""
    entity_id = "select.peblar_ev_charger_smart_charging"
    mock_peblar.smart_charging.side_effect = PeblarAuthenticationError(
        "Authentication error"
    )
    mock_peblar.login.side_effect = PeblarAuthenticationError("Authentication error")

    with pytest.raises(
        HomeAssistantError,
        match=(
            r"An authentication failure occurred while communicating "
            r"with the Peblar EV charger"
        ),
    ) as excinfo:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: "default",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "authentication_error"
    assert not excinfo.value.translation_placeholders

    # Ensure the device is reloaded on authentication error and triggers
    # a reauthentication flow.
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "method_name", "option", "expected_kwargs"),
    [
        (
            "select.peblar_ev_charger_buzzer_volume",
            "set_buzzer_volume",
            "medium",
            {"volume": SoundVolume.MEDIUM},
        ),
        (
            "select.peblar_ev_charger_led_brightness",
            "set_led_brightness",
            "bright",
            {"brightness": LedBrightness.BRIGHT},
        ),
    ],
)
async def test_select_hardware_entity(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    entity_id: str,
    method_name: str,
    option: str,
    expected_kwargs: dict,
) -> None:
    """Test the Peblar EV charger hardware select entities."""
    mocked_method = getattr(mock_peblar, method_name)
    mocked_method.reset_mock()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 1
    mocked_method.assert_called_with(**expected_kwargs)


@pytest.mark.parametrize(
    ("entity_unique_id_suffix", "hw_attr"),
    [
        ("buzzer_volume", "hardware_has_buzzer"),
        ("led_brightness", "hardware_has_led"),
    ],
)
async def test_hw_entity_absent_when_hw_flag_false(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    entity_unique_id_suffix: str,
    hw_attr: str,
) -> None:
    """Test hardware select entity is absent when the hardware flag is false."""
    setattr(mock_peblar.system_information.return_value, hw_attr, False)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            Platform.SELECT,
            DOMAIN,
            f"{mock_config_entry.unique_id}_{entity_unique_id_suffix}",
        )
        is None
    )
