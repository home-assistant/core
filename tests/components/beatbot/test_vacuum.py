"""Tests for the Beatbot vacuum entity (battery deprecation migration)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Protocol
from unittest.mock import AsyncMock, MagicMock

from beatbot_cloud import BeatbotAuthenticationError, BeatbotConnectionError
import pytest

from homeassistant.components.beatbot.iot.category import (
    VACUUM_FEATURES_BY_CATEGORY,
    ProductCategory,
    vacuum_activity,
    vacuum_features_from_capabilities,
)
from homeassistant.components.beatbot.iot.const import (
    INTERFACE_PAUSE,
    INTERFACE_RETURN_TO_BASE,
    INTERFACE_START,
    INTERFACE_VACUUM_STATE,
)
from homeassistant.components.beatbot.models import BeatbotCapability, BeatbotDeviceData
from homeassistant.components.beatbot.vacuum import BeatbotVacuum
from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

DEVICE_ID = "test-device-1"


class CoordinatorFactory(Protocol):
    """Create a minimal coordinator carrying a single device."""

    def __call__(
        self,
        category: str,
        *,
        work_mode_options: dict[int, str] | None = None,
        capabilities: dict[str, BeatbotCapability] | None = None,
    ) -> SimpleNamespace:
        """Create the coordinator."""


@pytest.fixture
def coordinator_factory() -> CoordinatorFactory:
    """Return a coordinator factory."""

    def _create(
        category: str,
        *,
        work_mode_options: dict[int, str] | None = None,
        capabilities: dict[str, BeatbotCapability] | None = None,
    ) -> SimpleNamespace:
        device = BeatbotDeviceData(
            device_id=DEVICE_ID,
            product_id="pool-bot-x",
            product_category=category,
            work_status=0,
            work_mode=0,
            error_code=0,
            battery_level=80,
            versions=[],
            is_online=True,
            work_mode_options=work_mode_options or {},
            capabilities=capabilities or {},
        )
        return SimpleNamespace(data={DEVICE_ID: device})

    return _create


@pytest.mark.parametrize(
    ("category", "expected_features"),
    [
        ("pool_clean_bot", {VacuumEntityFeature.STATE}),
        ("lawn_mower", {VacuumEntityFeature.STATE}),
    ],
)
def test_vacuum_no_deprecated_battery_feature(
    coordinator_factory: CoordinatorFactory,
    category: str,
    expected_features: set[VacuumEntityFeature],
) -> None:
    """Vacuum must not advertise the deprecated BATTERY feature."""
    vacuum = BeatbotVacuum(coordinator_factory(category), DEVICE_ID)

    assert VacuumEntityFeature.BATTERY not in vacuum.supported_features
    assert set(vacuum.supported_features) == expected_features
    # state_attributes must no longer carry battery level (triggers deprecation)
    assert ATTR_BATTERY_LEVEL not in vacuum.state_attributes


def test_category_table_has_no_battery_feature() -> None:
    """No category advertises the deprecated BATTERY feature."""
    for features in VACUUM_FEATURES_BY_CATEGORY.values():
        assert VacuumEntityFeature.BATTERY not in features


def test_clean_base_station_notice_does_not_set_vacuum_error(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """Informational station notices must not fault the vacuum entity."""
    coordinator = coordinator_factory("clean_base_station")
    coordinator.data[DEVICE_ID].error_code = 1 << 5

    vacuum = BeatbotVacuum(coordinator, DEVICE_ID)

    assert vacuum.activity is not VacuumActivity.ERROR


def test_clean_base_station_uses_its_own_translation(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """The station vacuum entity must not use the pool-cleaner name."""
    vacuum = BeatbotVacuum(coordinator_factory("clean_base_station"), DEVICE_ID)

    assert vacuum.translation_key == "beatbot_clean_base_station_vacuum"


def test_clean_base_station_fault_sets_vacuum_error(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """The five station fault bits must continue to set ERROR activity."""
    coordinator = coordinator_factory("clean_base_station")
    coordinator.data[DEVICE_ID].error_code = 1 << 4

    vacuum = BeatbotVacuum(coordinator, DEVICE_ID)

    assert vacuum.activity is VacuumActivity.ERROR


def test_clean_base_station_fault_wins_over_notice(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """A real fault must not be hidden when notice bits are also active."""
    coordinator = coordinator_factory("clean_base_station")
    coordinator.data[DEVICE_ID].error_code = (1 << 0) | (1 << 24)

    vacuum = BeatbotVacuum(coordinator, DEVICE_ID)

    assert vacuum.activity is VacuumActivity.ERROR


def test_vacuum_does_not_advertise_stop() -> None:
    """No device exposes vacuum.stop (the backend registers no such action)."""
    for features in VACUUM_FEATURES_BY_CATEGORY.values():
        assert VacuumEntityFeature.STOP not in features


def test_work_mode_is_not_exposed_as_vacuum_fan_speed(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """Work mode belongs to select.work_mode, not vacuum.set_fan_speed."""
    vacuum = BeatbotVacuum(
        coordinator_factory(
            "pool_clean_bot",
            work_mode_options={0: "fast", 2: "custom"},
        ),
        DEVICE_ID,
    )

    assert VacuumEntityFeature.FAN_SPEED not in vacuum.supported_features


def test_vacuum_features_derived_from_capabilities(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """Features must match the capabilities the backend actually advertises.

    A device reporting only vacuum.state (retrievable) + vacuum.start must
    advertise STATE|START and nothing else — pause/return are absent.
    """
    capabilities = {
        INTERFACE_VACUUM_STATE: BeatbotCapability(
            interface_info=INTERFACE_VACUUM_STATE,
            retrievable=True,
            non_controllable=True,
        ),
        INTERFACE_START: BeatbotCapability(
            interface_info=INTERFACE_START,
            non_controllable=False,
        ),
    }
    vacuum = BeatbotVacuum(
        coordinator_factory("pool_clean_bot", capabilities=capabilities),
        DEVICE_ID,
    )

    assert set(vacuum.supported_features) == {
        VacuumEntityFeature.STATE,
        VacuumEntityFeature.START,
    }
    assert VacuumEntityFeature.PAUSE not in vacuum.supported_features
    assert VacuumEntityFeature.RETURN_HOME not in vacuum.supported_features


def test_vacuum_features_omit_missing_action(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """No vacuum.start capability -> START must not be advertised."""
    capabilities = {
        INTERFACE_VACUUM_STATE: BeatbotCapability(
            interface_info=INTERFACE_VACUUM_STATE,
            retrievable=True,
            non_controllable=True,
        ),
        INTERFACE_PAUSE: BeatbotCapability(
            interface_info=INTERFACE_PAUSE,
            non_controllable=False,
        ),
        INTERFACE_RETURN_TO_BASE: BeatbotCapability(
            interface_info=INTERFACE_RETURN_TO_BASE,
            non_controllable=False,
        ),
    }
    vacuum = BeatbotVacuum(
        coordinator_factory("pool_clean_bot", capabilities=capabilities),
        DEVICE_ID,
    )

    assert VacuumEntityFeature.START not in vacuum.supported_features
    assert VacuumEntityFeature.PAUSE in vacuum.supported_features
    assert VacuumEntityFeature.RETURN_HOME in vacuum.supported_features


def test_vacuum_features_are_state_only_when_no_capabilities(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """Empty capabilities array must not infer unsupported actions."""
    vacuum = BeatbotVacuum(
        coordinator_factory("pool_clean_bot", capabilities={}),
        DEVICE_ID,
    )

    assert set(vacuum.supported_features) == {VacuumEntityFeature.STATE}


def test_vacuum_features_skip_readonly_action(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """An action flagged non_controllable=True is read-only, not advertised."""
    capabilities = {
        INTERFACE_VACUUM_STATE: BeatbotCapability(
            interface_info=INTERFACE_VACUUM_STATE,
            retrievable=True,
            non_controllable=True,
        ),
        # Present but read-only: must NOT become a Start button.
        INTERFACE_START: BeatbotCapability(
            interface_info=INTERFACE_START,
            non_controllable=True,
        ),
    }
    vacuum = BeatbotVacuum(
        coordinator_factory("pool_clean_bot", capabilities=capabilities),
        DEVICE_ID,
    )

    assert set(vacuum.supported_features) == {VacuumEntityFeature.STATE}
    assert VacuumEntityFeature.START not in vacuum.supported_features


def test_unknown_status_is_idle() -> None:
    """Unknown work states fall back to idle."""
    assert (
        vacuum_activity(ProductCategory.POOL_CLEAN_BOT, 999, 0) is VacuumActivity.IDLE
    )


def test_non_vacuum_capabilities_do_not_define_features() -> None:
    """Ignore capability sets that do not describe the vacuum platform."""
    capabilities = {
        "sensor.temperature": BeatbotCapability(
            interface_info="sensor.temperature",
            retrievable=True,
            non_controllable=True,
        )
    }

    assert vacuum_features_from_capabilities(capabilities) is None


@pytest.mark.parametrize(
    ("online", "last_update_success", "expected"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_vacuum_availability(
    coordinator_factory: CoordinatorFactory,
    online: bool,
    last_update_success: bool,
    expected: bool,
) -> None:
    """Require both an online device and a successful coordinator update."""
    coordinator = coordinator_factory("pool_clean_bot")
    coordinator.data[DEVICE_ID].is_online = online
    coordinator.last_update_success = last_update_success

    assert BeatbotVacuum(coordinator, DEVICE_ID).available is expected


def test_vacuum_device_info(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """Expose the Beatbot device metadata through the vacuum entity."""
    coordinator = coordinator_factory("pool_clean_bot")
    coordinator.data[DEVICE_ID].name = "AquaSense"
    coordinator.data[DEVICE_ID].model = "AquaSense 2"

    device_info = BeatbotVacuum(coordinator, DEVICE_ID).device_info

    assert device_info["identifiers"] == {("beatbot", DEVICE_ID)}
    assert device_info["name"] == "AquaSense"
    assert device_info["manufacturer"] == "Beatbot"
    assert device_info["model"] == "AquaSense 2"


@pytest.mark.parametrize(
    ("method", "interface"),
    [
        ("async_start", INTERFACE_START),
        ("async_pause", INTERFACE_PAUSE),
        ("async_return_to_base", INTERFACE_RETURN_TO_BASE),
    ],
)
async def test_vacuum_action_triggers_single_device_refresh(
    coordinator_factory: CoordinatorFactory,
    method: str,
    interface: str,
) -> None:
    """Refresh only the controlled device after a control command.

    Do not run the full discovery and batch-state refresh.
    """
    coordinator = coordinator_factory("pool_clean_bot")
    coordinator.api = SimpleNamespace(
        send_action=AsyncMock(),
    )
    coordinator.async_schedule_device_state_refresh = MagicMock()
    vacuum = BeatbotVacuum(coordinator, DEVICE_ID)

    await getattr(vacuum, method)()

    coordinator.api.send_action.assert_awaited_once_with(DEVICE_ID, interface)
    coordinator.async_schedule_device_state_refresh.assert_called_once_with(DEVICE_ID)


async def test_vacuum_action_rejects_offline_device(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """Raise a translated error without sending a command while offline."""
    coordinator = coordinator_factory("pool_clean_bot")
    coordinator.data[DEVICE_ID].is_online = False
    coordinator.api = SimpleNamespace(send_action=AsyncMock())
    coordinator.async_schedule_device_state_refresh = MagicMock()
    vacuum = BeatbotVacuum(coordinator, DEVICE_ID)

    with pytest.raises(HomeAssistantError) as exc_info:
        await vacuum.async_start()

    assert exc_info.value.translation_key == "device_offline"
    coordinator.api.send_action.assert_not_awaited()
    coordinator.async_schedule_device_state_refresh.assert_not_called()


async def test_vacuum_action_triggers_reauth(
    hass: HomeAssistant,
    coordinator_factory: CoordinatorFactory,
) -> None:
    """Start reauthentication when a control command rejects the token."""
    coordinator = coordinator_factory("pool_clean_bot")
    coordinator.api = SimpleNamespace(
        send_action=AsyncMock(side_effect=BeatbotAuthenticationError),
    )
    coordinator.config_entry = SimpleNamespace(async_start_reauth=MagicMock())
    coordinator.async_schedule_device_state_refresh = MagicMock()
    vacuum = BeatbotVacuum(coordinator, DEVICE_ID)
    vacuum.hass = hass

    with pytest.raises(ConfigEntryAuthFailed):
        await vacuum.async_start()

    coordinator.config_entry.async_start_reauth.assert_called_once_with(hass)
    coordinator.async_schedule_device_state_refresh.assert_not_called()


async def test_vacuum_action_translates_connection_error(
    coordinator_factory: CoordinatorFactory,
) -> None:
    """Translate control transport failures into a user-facing error."""
    coordinator = coordinator_factory("pool_clean_bot")
    coordinator.api = SimpleNamespace(
        send_action=AsyncMock(side_effect=BeatbotConnectionError),
    )
    coordinator.async_schedule_device_state_refresh = MagicMock()
    vacuum = BeatbotVacuum(coordinator, DEVICE_ID)

    with pytest.raises(HomeAssistantError) as exc_info:
        await vacuum.async_start()

    assert exc_info.value.translation_key == "control_connection_error"
    coordinator.async_schedule_device_state_refresh.assert_not_called()
