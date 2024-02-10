"""The tests for the climate component."""
from __future__ import annotations

from enum import Enum
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components import climate
from homeassistant.components.climate import (
    DOMAIN,
    SET_TEMPERATURE_SCHEMA,
    ClimateEntity,
    HVACMode,
)
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    ClimateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockModule,
    MockPlatform,
    async_mock_service,
    help_test_all,
    import_and_test_deprecated_constant,
    import_and_test_deprecated_constant_enum,
    mock_integration,
    mock_platform,
)


async def test_set_temp_schema_no_req(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with missing required data."""
    domain = "climate"
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {"hvac_mode": "off", "entity_id": ["climate.test_id"]}
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_set_temp_schema(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with ok required data."""
    domain = "climate"
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {"temperature": 20.0, "hvac_mode": "heat", "entity_id": ["climate.test_id"]}
    await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data == data


class MockClimateEntity(MockEntity, ClimateEntity):
    """Mock Climate device to use in tests."""

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_preset_mode = "home"
    _attr_preset_modes = ["home", "away"]
    _attr_fan_mode = "auto"
    _attr_fan_modes = ["auto", "off"]
    _attr_swing_mode = "auto"
    _attr_swing_modes = ["auto", "off"]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVACMode.*.
        """
        return HVACMode.HEAT

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVACMode.OFF, HVACMode.HEAT]

    def turn_on(self) -> None:
        """Turn on."""

    def turn_off(self) -> None:
        """Turn off."""

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._attr_preset_mode = preset_mode

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        self._attr_fan_mode = fan_mode

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        self._attr_swing_mode = swing_mode


async def test_sync_turn_on(hass: HomeAssistant) -> None:
    """Test if async turn_on calls sync turn_on."""
    climate = MockClimateEntity()
    climate.hass = hass

    climate.turn_on = MagicMock()
    await climate.async_turn_on()

    assert climate.turn_on.called


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    climate = MockClimateEntity()
    climate.hass = hass

    climate.turn_off = MagicMock()
    await climate.async_turn_off()

    assert climate.turn_off.called


def _create_tuples(enum: Enum, constant_prefix: str) -> list[tuple[Enum, str]]:
    result = []
    for enum in enum:
        if enum not in [ClimateEntityFeature.TURN_ON, ClimateEntityFeature.TURN_OFF]:
            result.append((enum, constant_prefix))
    return result


@pytest.mark.parametrize(
    "module",
    [climate, climate.const],
)
def test_all(module: ModuleType) -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(module)


@pytest.mark.parametrize(
    ("enum", "constant_prefix"),
    _create_tuples(climate.ClimateEntityFeature, "SUPPORT_")
    + _create_tuples(climate.HVACMode, "HVAC_MODE_"),
)
@pytest.mark.parametrize(
    "module",
    [climate, climate.const],
)
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: Enum,
    constant_prefix: str,
    module: ModuleType,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, module, enum, constant_prefix, "2025.1"
    )


@pytest.mark.parametrize(
    ("enum", "constant_postfix"),
    [
        (climate.HVACAction.OFF, "OFF"),
        (climate.HVACAction.HEATING, "HEAT"),
        (climate.HVACAction.COOLING, "COOL"),
        (climate.HVACAction.DRYING, "DRY"),
        (climate.HVACAction.IDLE, "IDLE"),
        (climate.HVACAction.FAN, "FAN"),
    ],
)
def test_deprecated_current_constants(
    caplog: pytest.LogCaptureFixture,
    enum: climate.HVACAction,
    constant_postfix: str,
) -> None:
    """Test deprecated current constants."""
    import_and_test_deprecated_constant(
        caplog,
        climate.const,
        "CURRENT_HVAC_" + constant_postfix,
        f"{enum.__class__.__name__}.{enum.name}",
        enum,
        "2025.1",
    )


async def test_preset_mode_validation(
    hass: HomeAssistant, config_flow_fixture: None
) -> None:
    """Test mode validation for fan, swing and preset."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_climate_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test climate platform via config entry."""
        async_add_entities([MockClimateEntity(name="test", entity_id="climate.test")])

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
        "test.climate",
        MockPlatform(async_setup_entry=async_setup_entry_climate_platform),
    )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.test")
    assert state.attributes.get(ATTR_PRESET_MODE) == "home"
    assert state.attributes.get(ATTR_FAN_MODE) == "auto"
    assert state.attributes.get(ATTR_SWING_MODE) == "auto"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            "entity_id": "climate.test",
            "preset_mode": "away",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SWING_MODE,
        {
            "entity_id": "climate.test",
            "swing_mode": "off",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            "entity_id": "climate.test",
            "fan_mode": "off",
        },
        blocking=True,
    )
    state = hass.states.get("climate.test")
    assert state.attributes.get(ATTR_PRESET_MODE) == "away"
    assert state.attributes.get(ATTR_FAN_MODE) == "off"
    assert state.attributes.get(ATTR_SWING_MODE) == "off"

    with pytest.raises(
        ServiceValidationError,
        match="The preset_mode invalid is not a valid preset_mode: home, away",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                "entity_id": "climate.test",
                "preset_mode": "invalid",
            },
            blocking=True,
        )
    assert (
        str(exc.value)
        == "The preset_mode invalid is not a valid preset_mode: home, away"
    )
    assert exc.value.translation_key == "not_valid_preset_mode"

    with pytest.raises(
        ServiceValidationError,
        match="The swing_mode invalid is not a valid swing_mode: auto, off",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SWING_MODE,
            {
                "entity_id": "climate.test",
                "swing_mode": "invalid",
            },
            blocking=True,
        )
    assert (
        str(exc.value) == "The swing_mode invalid is not a valid swing_mode: auto, off"
    )
    assert exc.value.translation_key == "not_valid_swing_mode"

    with pytest.raises(
        ServiceValidationError,
        match="The fan_mode invalid is not a valid fan_mode: auto, off",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                "entity_id": "climate.test",
                "fan_mode": "invalid",
            },
            blocking=True,
        )
    assert str(exc.value) == "The fan_mode invalid is not a valid fan_mode: auto, off"
    assert exc.value.translation_key == "not_valid_fan_mode"


def test_deprecated_supported_features_ints(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated supported features ints."""

    class MockClimateEntity(ClimateEntity):
        @property
        def supported_features(self) -> int:
            """Return supported features."""
            return 1

    entity = MockClimateEntity()
    assert entity.supported_features is ClimateEntityFeature(1)
    assert "MockClimateEntity" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "ClimateEntityFeature.TARGET_TEMPERATURE" in caplog.text
    caplog.clear()
    assert entity.supported_features is ClimateEntityFeature(1)
    assert "is using deprecated supported features values" not in caplog.text


async def test_warning_not_implemented_turn_on_off_feature(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, config_flow_fixture: None
) -> None:
    """Test adding feature flag and warn if missing when methods are set."""

    called = []

    class MockClimateEntityTest(MockClimateEntity):
        """Mock Climate device."""

        def turn_on(self) -> None:
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

    async def async_setup_entry_climate_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test climate platform via config entry."""
        async_add_entities(
            [MockClimateEntityTest(name="test", entity_id="climate.test")]
        )

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
        "test.climate",
        MockPlatform(async_setup_entry=async_setup_entry_climate_platform),
    )

    with patch.object(
        MockClimateEntityTest, "__module__", "tests.custom_components.climate.test_init"
    ):
        config_entry = MockConfigEntry(domain="test")
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.test")
    assert state is not None

    assert (
        "Entity climate.test (<class 'tests.custom_components.climate.test_init."
        "test_warning_not_implemented_turn_on_off_feature.<locals>.MockClimateEntityTest'>)"
        " does not set ClimateEntityFeature.TURN_OFF but implements the turn_off method."
        " Please report it to the author of the 'test' custom integration"
        in caplog.text
    )
    assert (
        "Entity climate.test (<class 'tests.custom_components.climate.test_init."
        "test_warning_not_implemented_turn_on_off_feature.<locals>.MockClimateEntityTest'>)"
        " does not set ClimateEntityFeature.TURN_ON but implements the turn_on method."
        " Please report it to the author of the 'test' custom integration"
        in caplog.text
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {
            "entity_id": "climate.test",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {
            "entity_id": "climate.test",
        },
        blocking=True,
    )

    assert len(called) == 2
    assert "turn_on" in called
    assert "turn_off" in called


async def test_implicit_warning_not_implemented_turn_on_off_feature(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, config_flow_fixture: None
) -> None:
    """Test adding feature flag and warn if missing when methods are not set.

    (implicit by hvac mode)
    """

    class MockClimateEntityTest(MockEntity, ClimateEntity):
        """Mock Climate device."""

        _attr_temperature_unit = UnitOfTemperature.CELSIUS

        @property
        def hvac_mode(self) -> HVACMode:
            """Return hvac operation ie. heat, cool mode.

            Need to be one of HVACMode.*.
            """
            return HVACMode.HEAT

        @property
        def hvac_modes(self) -> list[HVACMode]:
            """Return the list of available hvac operation modes.

            Need to be a subset of HVAC_MODES.
            """
            return [HVACMode.OFF, HVACMode.HEAT]

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_climate_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test climate platform via config entry."""
        async_add_entities(
            [MockClimateEntityTest(name="test", entity_id="climate.test")]
        )

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
        "test.climate",
        MockPlatform(async_setup_entry=async_setup_entry_climate_platform),
    )

    with patch.object(
        MockClimateEntityTest, "__module__", "tests.custom_components.climate.test_init"
    ):
        config_entry = MockConfigEntry(domain="test")
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.test")
    assert state is not None

    assert (
        "Entity climate.test (<class 'tests.custom_components.climate.test_init."
        "test_implicit_warning_not_implemented_turn_on_off_feature.<locals>.MockClimateEntityTest'>)"
        " implements HVACMode(s): off, heat and therefore implicitly supports the turn_on/turn_off"
        " methods without setting the proper ClimateEntityFeature. Please report it to the author"
        " of the 'test' custom integration" in caplog.text
    )


async def test_no_warning_implemented_turn_on_off_feature(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, config_flow_fixture: None
) -> None:
    """Test no warning when feature flags are set."""

    class MockClimateEntityTest(MockClimateEntity):
        """Mock Climate device."""

        _attr_supported_features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_climate_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test climate platform via config entry."""
        async_add_entities(
            [MockClimateEntityTest(name="test", entity_id="climate.test")]
        )

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
        "test.climate",
        MockPlatform(async_setup_entry=async_setup_entry_climate_platform),
    )

    with patch.object(
        MockClimateEntityTest, "__module__", "tests.custom_components.climate.test_init"
    ):
        config_entry = MockConfigEntry(domain="test")
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.test")
    assert state is not None

    assert (
        "does not set ClimateEntityFeature.TURN_OFF but implements the turn_off method."
        not in caplog.text
    )
    assert (
        "does not set ClimateEntityFeature.TURN_ON but implements the turn_on method."
        not in caplog.text
    )
    assert (
        " implements HVACMode(s): off, heat and therefore implicitly supports the off, heat methods"
        not in caplog.text
    )


async def test_no_warning_integration_has_migrated(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, config_flow_fixture: None
) -> None:
    """Test no warning when integration migrated using `_enable_turn_on_off_backwards_compatibility`."""

    class MockClimateEntityTest(MockClimateEntity):
        """Mock Climate device."""

        _enable_turn_on_off_backwards_compatibility = False
        _attr_supported_features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
        )

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_climate_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test climate platform via config entry."""
        async_add_entities(
            [MockClimateEntityTest(name="test", entity_id="climate.test")]
        )

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
        "test.climate",
        MockPlatform(async_setup_entry=async_setup_entry_climate_platform),
    )

    with patch.object(
        MockClimateEntityTest, "__module__", "tests.custom_components.climate.test_init"
    ):
        config_entry = MockConfigEntry(domain="test")
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.test")
    assert state is not None

    assert (
        "does not set ClimateEntityFeature.TURN_OFF but implements the turn_off method."
        not in caplog.text
    )
    assert (
        "does not set ClimateEntityFeature.TURN_ON but implements the turn_on method."
        not in caplog.text
    )
    assert (
        " implements HVACMode(s): off, heat and therefore implicitly supports the off, heat methods"
        not in caplog.text
    )
