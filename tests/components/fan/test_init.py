"""Tests for fan platforms."""

from unittest.mock import patch

import pytest

from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN,
    SERVICE_SET_PRESET_MODE,
    FanEntity,
    FanEntityFeature,
    NotValidPresetModeError,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component

from .common import MockFan

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    help_test_all,
    import_and_test_deprecated_constant_enum,
    mock_integration,
    mock_platform,
    setup_test_component_platform,
)


class BaseFan(FanEntity):
    """Implementation of the abstract FanEntity."""

    def __init__(self) -> None:
        """Initialize the fan."""


def test_fanentity() -> None:
    """Test fan entity methods."""
    fan = BaseFan()
    assert fan.state == "off"
    assert fan.preset_modes is None
    assert fan.supported_features == 0
    assert fan.percentage_step == 1
    assert fan.speed_count == 100
    assert fan.capability_attributes == {}
    # Test set_speed not required
    with pytest.raises(NotImplementedError):
        fan.oscillate(True)
    with pytest.raises(AttributeError):
        fan.set_speed("low")
    with pytest.raises(NotImplementedError):
        fan.set_percentage(0)
    with pytest.raises(NotImplementedError):
        fan.set_preset_mode("auto")
    with pytest.raises(NotImplementedError):
        fan.turn_on()
    with pytest.raises(NotImplementedError):
        fan.turn_off()


async def test_async_fanentity(hass: HomeAssistant) -> None:
    """Test async fan entity methods."""
    fan = BaseFan()
    fan.hass = hass
    assert fan.state == "off"
    assert fan.preset_modes is None
    assert fan.supported_features == 0
    assert fan.percentage_step == 1
    assert fan.speed_count == 100
    assert fan.capability_attributes == {}
    # Test set_speed not required
    with pytest.raises(NotImplementedError):
        await fan.async_oscillate(True)
    with pytest.raises(AttributeError):
        await fan.async_set_speed("low")
    with pytest.raises(NotImplementedError):
        await fan.async_set_percentage(0)
    with pytest.raises(NotImplementedError):
        await fan.async_set_preset_mode("auto")
    with pytest.raises(NotImplementedError):
        await fan.async_turn_on()
    with pytest.raises(NotImplementedError):
        await fan.async_turn_off()
    with pytest.raises(NotImplementedError):
        await fan.async_increase_speed()
    with pytest.raises(NotImplementedError):
        await fan.async_decrease_speed()


@pytest.mark.parametrize(
    ("attribute_name", "attribute_value"),
    [
        ("current_direction", "forward"),
        ("oscillating", True),
        ("percentage", 50),
        ("preset_mode", "medium"),
        ("preset_modes", ["low", "medium", "high"]),
        ("speed_count", 50),
        ("supported_features", 1),
    ],
)
def test_fanentity_attributes(attribute_name, attribute_value) -> None:
    """Test fan entity attribute shorthand."""
    fan = BaseFan()
    setattr(fan, f"_attr_{attribute_name}", attribute_value)
    assert getattr(fan, attribute_name) == attribute_value


async def test_preset_mode_validation(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test preset mode validation."""
    await hass.async_block_till_done()

    test_fan = MockFan(
        name="Support fan with preset_mode support",
        supported_features=FanEntityFeature.PRESET_MODE,
        unique_id="unique_support_preset_mode",
        preset_modes=["auto", "eco"],
    )
    setup_test_component_platform(hass, "fan", [test_fan])

    assert await async_setup_component(hass, "fan", {"fan": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("fan.support_fan_with_preset_mode_support")
    assert state.attributes.get(ATTR_PRESET_MODES) == ["auto", "eco"]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            "entity_id": "fan.support_fan_with_preset_mode_support",
            "preset_mode": "eco",
        },
        blocking=True,
    )

    state = hass.states.get("fan.support_fan_with_preset_mode_support")
    assert state.attributes.get(ATTR_PRESET_MODE) == "eco"

    with pytest.raises(NotValidPresetModeError) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                "entity_id": "fan.support_fan_with_preset_mode_support",
                "preset_mode": "invalid",
            },
            blocking=True,
        )
    assert exc.value.translation_key == "not_valid_preset_mode"

    with pytest.raises(NotValidPresetModeError) as exc:
        await test_fan._valid_preset_mode_or_raise("invalid")
    assert exc.value.translation_key == "not_valid_preset_mode"


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(fan)


@pytest.mark.parametrize(("enum"), list(fan.FanEntityFeature))
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: fan.FanEntityFeature,
) -> None:
    """Test deprecated constants."""
    if not FanEntityFeature.TURN_OFF and not FanEntityFeature.TURN_ON:
        import_and_test_deprecated_constant_enum(
            caplog, fan, enum, "SUPPORT_", "2025.1"
        )


def test_deprecated_supported_features_ints(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated supported features ints."""

    class MockFan(FanEntity):
        @property
        def supported_features(self) -> int:
            """Return supported features."""
            return 1

    entity = MockFan()
    assert entity.supported_features is FanEntityFeature(1)
    assert "MockFan" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "FanEntityFeature.SET_SPEED" in caplog.text
    caplog.clear()
    assert entity.supported_features is FanEntityFeature(1)
    assert "is using deprecated supported features values" not in caplog.text


async def test_warning_not_implemented_turn_on_off_feature(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, config_flow_fixture: None
) -> None:
    """Test adding feature flag and warn if missing when methods are set."""

    called = []

    class MockFanEntityTest(MockFan):
        """Mock Fan device."""

        def turn_on(
            self,
            percentage: int | None = None,
            preset_mode: str | None = None,
        ) -> None:
            """Turn on."""
            called.append("turn_on")

        def turn_off(self) -> None:
            """Turn off."""
            called.append("turn_off")

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_fan_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test fan platform via config entry."""
        async_add_entities([MockFanEntityTest(name="test", entity_id="fan.test")])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
        ),
        built_in=False,
    )
    mock_platform(
        hass,
        "test.fan",
        MockPlatform(async_setup_entry=async_setup_entry_fan_platform),
    )

    with patch.object(
        MockFanEntityTest, "__module__", "tests.custom_components.fan.test_init"
    ):
        config_entry = MockConfigEntry(domain="test")
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state is not None

    assert (
        "Entity fan.test (<class 'tests.custom_components.fan.test_init.test_warning_not_implemented_turn_on_off_feature.<locals>.MockFanEntityTest'>) "
        "does not set FanEntityFeature.TURN_OFF but implements the turn_off method. Please report it to the author of the 'test' custom integration"
        in caplog.text
    )
    assert (
        "Entity fan.test (<class 'tests.custom_components.fan.test_init.test_warning_not_implemented_turn_on_off_feature.<locals>.MockFanEntityTest'>) "
        "does not set FanEntityFeature.TURN_ON but implements the turn_on method. Please report it to the author of the 'test' custom integration"
        in caplog.text
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {
            "entity_id": "fan.test",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {
            "entity_id": "fan.test",
        },
        blocking=True,
    )

    assert len(called) == 2
    assert "turn_on" in called
    assert "turn_off" in called


async def test_no_warning_implemented_turn_on_off_feature(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, config_flow_fixture: None
) -> None:
    """Test no warning when feature flags are set."""

    class MockFanEntityTest(MockFan):
        """Mock Fan device."""

        _attr_supported_features = (
            FanEntityFeature.DIRECTION
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_fan_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test fan platform via config entry."""
        async_add_entities([MockFanEntityTest(name="test", entity_id="fan.test")])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
        ),
        built_in=False,
    )
    mock_platform(
        hass,
        "test.fan",
        MockPlatform(async_setup_entry=async_setup_entry_fan_platform),
    )

    with patch.object(
        MockFanEntityTest, "__module__", "tests.custom_components.fan.test_init"
    ):
        config_entry = MockConfigEntry(domain="test")
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state is not None

    assert "does not set FanEntityFeature.TURN_OFF" not in caplog.text
    assert "does not set FanEntityFeature.TURN_ON" not in caplog.text


async def test_no_warning_integration_has_migrated(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, config_flow_fixture: None
) -> None:
    """Test no warning when integration migrated using `_enable_turn_on_off_backwards_compatibility`."""

    class MockFanEntityTest(MockFan):
        """Mock Fan device."""

        _enable_turn_on_off_backwards_compatibility = False
        _attr_supported_features = (
            FanEntityFeature.DIRECTION
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
        )

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_fan_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test fan platform via config entry."""
        async_add_entities([MockFanEntityTest(name="test", entity_id="fan.test")])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
        ),
        built_in=False,
    )
    mock_platform(
        hass,
        "test.fan",
        MockPlatform(async_setup_entry=async_setup_entry_fan_platform),
    )

    with patch.object(
        MockFanEntityTest, "__module__", "tests.custom_components.fan.test_init"
    ):
        config_entry = MockConfigEntry(domain="test")
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state is not None

    assert "does not set FanEntityFeature.TURN_OFF" not in caplog.text
    assert "does not set FanEntityFeature.TURN_ON" not in caplog.text


async def test_no_warning_integration_implement_feature_flags(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, config_flow_fixture: None
) -> None:
    """Test no warning when integration uses the correct feature flags."""

    class MockFanEntityTest(MockFan):
        """Mock Fan device."""

        _attr_supported_features = (
            FanEntityFeature.DIRECTION
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_fan_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test fan platform via config entry."""
        async_add_entities([MockFanEntityTest(name="test", entity_id="fan.test")])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
        ),
        built_in=False,
    )
    mock_platform(
        hass,
        "test.fan",
        MockPlatform(async_setup_entry=async_setup_entry_fan_platform),
    )

    with patch.object(
        MockFanEntityTest, "__module__", "tests.custom_components.fan.test_init"
    ):
        config_entry = MockConfigEntry(domain="test")
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state is not None

    assert "does not set FanEntityFeature.TURN_OFF" not in caplog.text
    assert "does not set FanEntityFeature.TURN_ON" not in caplog.text
