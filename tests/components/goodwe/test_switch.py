"""Test the GoodWe switch platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
from goodwe import InverterError, SensorKind
from goodwe.exceptions import RequestRejectedException
from goodwe.sensor import Integer
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.goodwe.const import (
    CONF_MODEL_FAMILY,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_HOST, TEST_PORT, TEST_SERIAL

FAST_CHARGING = "fast_charging"
FAST_CHARGING_ENTITY_ID = "switch.goodwe_fast_charging"

# Setting definition as advertised by the goodwe library for ET inverters
FAST_CHARGING_SETTING = Integer(
    FAST_CHARGING, 47545, "Fast Charging Enabled", "", SensorKind.BAT
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked GoodWe config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=2,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_MODEL_FAMILY: "ET",
        },
        unique_id=TEST_SERIAL,
    )


def configure_settings(
    mock_inverter: MagicMock, settings: dict[str, Any], advertised: bool = True
) -> None:
    """Configure the settings advertised and readable on the mocked inverter."""
    mock_inverter.settings.return_value = (
        (FAST_CHARGING_SETTING,) if advertised and FAST_CHARGING in settings else ()
    )

    async def read_setting(setting_id: str) -> Any:
        if setting_id not in settings:
            raise ValueError(f'Unknown setting "{setting_id}"')
        if isinstance(settings[setting_id], Exception):
            raise settings[setting_id]
        return settings[setting_id]

    async def write_setting(setting_id: str, value: Any) -> None:
        settings[setting_id] = value

    mock_inverter.read_setting = AsyncMock(side_effect=read_setting)
    mock_inverter.write_setting = AsyncMock(side_effect=write_setting)


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the GoodWe integration with only the switch platform."""
    entry.add_to_hass(hass)
    with patch("homeassistant.components.goodwe.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("current_value", "expected_state"), [(0, STATE_OFF), (1, STATE_ON)]
)
async def test_fast_charging(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
    current_value: int,
    expected_state: str,
) -> None:
    """Test the fast charging entity is created from the setting."""
    configure_settings(mock_inverter, {FAST_CHARGING: current_value})
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FAST_CHARGING_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state

    entry = entity_registry.async_get(FAST_CHARGING_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{FAST_CHARGING}-{TEST_SERIAL}"
    assert entry.entity_category is EntityCategory.CONFIG
    assert entry.translation_key == FAST_CHARGING


async def test_fast_charging_not_advertised(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no entity is created and no read is attempted without the setting."""
    configure_settings(mock_inverter, {FAST_CHARGING: 0}, advertised=False)
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FAST_CHARGING_ENTITY_ID) is None
    assert call(FAST_CHARGING) not in mock_inverter.read_setting.call_args_list


@pytest.mark.parametrize(
    "read_result",
    [InverterError("Failed to read setting"), ValueError("Unknown setting"), None],
    ids=["inverter_error", "value_error", "rejected"],
)
async def test_fast_charging_read_error(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
    read_result: Exception | None,
) -> None:
    """Test the entity is omitted when the advertised setting cannot be read."""
    configure_settings(mock_inverter, {FAST_CHARGING: read_result})
    await setup_integration(hass, mock_config_entry)

    mock_inverter.read_setting.assert_any_call(FAST_CHARGING)
    assert hass.states.get(FAST_CHARGING_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("current_value", "service", "written_value", "expected_state"),
    [
        (0, SERVICE_TURN_ON, 1, STATE_ON),
        (1, SERVICE_TURN_OFF, 0, STATE_OFF),
    ],
)
async def test_switch_fast_charging(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
    current_value: int,
    service: str,
    written_value: int,
    expected_state: str,
) -> None:
    """Test turning fast charging on and off writes the setting."""
    configure_settings(mock_inverter, {FAST_CHARGING: current_value})
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: FAST_CHARGING_ENTITY_ID},
        blocking=True,
    )

    mock_inverter.write_setting.assert_called_once_with(FAST_CHARGING, written_value)
    assert hass.states.get(FAST_CHARGING_ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    ("error", "expected_error", "translation_key"),
    [
        (
            InverterError("Failed to write setting"),
            HomeAssistantError,
            "write_failed",
        ),
        (
            RequestRejectedException("ILLEGAL DATA VALUE"),
            ServiceValidationError,
            "setting_rejected",
        ),
    ],
    ids=["inverter_error", "rejected"],
)
async def test_switch_fast_charging_write_error(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected_error: type[HomeAssistantError],
    translation_key: str,
) -> None:
    """Test the state is not updated when writing the setting fails."""
    configure_settings(mock_inverter, {FAST_CHARGING: 0})
    await setup_integration(hass, mock_config_entry)
    mock_inverter.write_setting.side_effect = error

    with pytest.raises(expected_error) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: FAST_CHARGING_ENTITY_ID},
            blocking=True,
        )

    assert type(exc_info.value) is expected_error
    assert exc_info.value.translation_key == translation_key
    mock_inverter.write_setting.assert_called_once_with(FAST_CHARGING, 1)
    assert hass.states.get(FAST_CHARGING_ENTITY_ID).state == STATE_OFF


async def test_fast_charging_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the polled state follows the inverter and its availability."""
    settings: dict[str, Any] = {FAST_CHARGING: 1}
    configure_settings(mock_inverter, settings)
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(FAST_CHARGING_ENTITY_ID).state == STATE_ON

    async def poll() -> None:
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # Changed on the inverter itself
    settings[FAST_CHARGING] = 0
    await poll()
    assert hass.states.get(FAST_CHARGING_ENTITY_ID).state == STATE_OFF

    # Inverter unreachable or rejecting the read
    settings[FAST_CHARGING] = InverterError("Failed to read setting")
    await poll()
    assert hass.states.get(FAST_CHARGING_ENTITY_ID).state == STATE_UNAVAILABLE
    settings[FAST_CHARGING] = None
    await poll()
    assert hass.states.get(FAST_CHARGING_ENTITY_ID).state == STATE_UNAVAILABLE

    # Recovered
    settings[FAST_CHARGING] = 1
    await poll()
    assert hass.states.get(FAST_CHARGING_ENTITY_ID).state == STATE_ON
