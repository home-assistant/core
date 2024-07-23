"""The tests for the climate component."""

from __future__ import annotations

from enum import Enum
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

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
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
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

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._attr_preset_mode = preset_mode

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        self._attr_fan_mode = fan_mode

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        self._attr_swing_mode = swing_mode


class MockClimateEntityTestMethods(MockClimateEntity):
    """Mock Climate device."""

    def turn_on(self) -> None:
        """Turn on."""

    def turn_off(self) -> None:
        """Turn off."""


async def test_sync_turn_on(hass: HomeAssistant) -> None:
    """Test if async turn_on calls sync turn_on."""
    climate = MockClimateEntityTestMethods()
    climate.hass = hass

    climate.turn_on = MagicMock()
    await climate.async_turn_on()

    assert climate.turn_on.called


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    climate = MockClimateEntityTestMethods()
    climate.hass = hass

    climate.turn_off = MagicMock()
    await climate.async_turn_off()

    assert climate.turn_off.called


def _create_tuples(enum: Enum, constant_prefix: str) -> list[tuple[Enum, str]]:
    return [
        (enum_field, constant_prefix)
        for enum_field in enum
        if enum_field
        not in [ClimateEntityFeature.TURN_ON, ClimateEntityFeature.TURN_OFF]
    ]


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
        match="Preset mode invalid is not valid. Valid preset modes are: home, away",
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
        == "Preset mode invalid is not valid. Valid preset modes are: home, away"
    )
    assert exc.value.translation_key == "not_valid_preset_mode"

    with pytest.raises(
        ServiceValidationError,
        match="Swing mode invalid is not valid. Valid swing modes are: auto, off",
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
        str(exc.value)
        == "Swing mode invalid is not valid. Valid swing modes are: auto, off"
    )
    assert exc.value.translation_key == "not_valid_swing_mode"

    with pytest.raises(
        ServiceValidationError,
        match="Fan mode invalid is not valid. Valid fan modes are: auto, off",
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
    assert (
        str(exc.value)
        == "Fan mode invalid is not valid. Valid fan modes are: auto, off"
    )
    assert exc.value.translation_key == "not_valid_fan_mode"


@pytest.mark.parametrize(
    "supported_features_at_int",
    [
        ClimateEntityFeature.TARGET_TEMPERATURE.value,
        ClimateEntityFeature.TARGET_TEMPERATURE.value
        | ClimateEntityFeature.TURN_ON.value
        | ClimateEntityFeature.TURN_OFF.value,
    ],
)
def test_deprecated_supported_features_ints(
    caplog: pytest.LogCaptureFixture, supported_features_at_int: int
) -> None:
    """Test deprecated supported features ints."""

    class MockClimateEntity(ClimateEntity):
        @property
        def supported_features(self) -> int:
            """Return supported features."""
            return supported_features_at_int

    entity = MockClimateEntity()
    assert entity.supported_features is ClimateEntityFeature(supported_features_at_int)
    assert "MockClimateEntity" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "ClimateEntityFeature.TARGET_TEMPERATURE" in caplog.text
    caplog.clear()
    assert entity.supported_features is ClimateEntityFeature(supported_features_at_int)
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


async def test_turn_on_off_toggle(hass: HomeAssistant) -> None:
    """Test turn_on/turn_off/toggle methods."""

    class MockClimateEntityTest(MockClimateEntity):
        """Mock Climate device."""

        _attr_hvac_mode = HVACMode.OFF

        @property
        def hvac_mode(self) -> HVACMode:
            """Return hvac mode."""
            return self._attr_hvac_mode

        async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
            """Set new target hvac mode."""
            self._attr_hvac_mode = hvac_mode

    climate = MockClimateEntityTest()
    climate.hass = hass

    await climate.async_turn_on()
    assert climate.hvac_mode == HVACMode.HEAT

    await climate.async_turn_off()
    assert climate.hvac_mode == HVACMode.OFF

    await climate.async_toggle()
    assert climate.hvac_mode == HVACMode.HEAT
    await climate.async_toggle()
    assert climate.hvac_mode == HVACMode.OFF


async def test_sync_toggle(hass: HomeAssistant) -> None:
    """Test if async toggle calls sync toggle."""

    class MockClimateEntityTest(MockClimateEntity):
        """Mock Climate device."""

        _enable_turn_on_off_backwards_compatibility = False
        _attr_supported_features = (
            ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        )

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

        def toggle(self) -> None:
            """Toggle."""

    climate = MockClimateEntityTest()
    climate.hass = hass

    climate.toggle = Mock()
    await climate.async_toggle()

    assert climate.toggle.called


ISSUE_TRACKER = "https://blablabla.com"


@pytest.mark.parametrize(
    (
        "manifest_extra",
        "translation_key",
        "translation_placeholders_extra",
        "report",
        "module",
    ),
    [
        (
            {},
            "deprecated_climate_aux_no_url",
            {},
            "report it to the author of the 'test' custom integration",
            "custom_components.test.climate",
        ),
        (
            {"issue_tracker": ISSUE_TRACKER},
            "deprecated_climate_aux_url_custom",
            {"issue_tracker": ISSUE_TRACKER},
            "create a bug report at https://blablabla.com",
            "custom_components.test.climate",
        ),
    ],
)
async def test_issue_aux_property_deprecated(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_flow_fixture: None,
    manifest_extra: dict[str, str],
    translation_key: str,
    translation_placeholders_extra: dict[str, str],
    report: str,
    module: str,
) -> None:
    """Test the issue is raised on deprecated auxiliary heater attributes."""

    class MockClimateEntityWithAux(MockClimateEntity):
        """Mock climate class with mocked aux heater."""

        _attr_supported_features = (
            ClimateEntityFeature.AUX_HEAT | ClimateEntityFeature.TARGET_TEMPERATURE
        )

        @property
        def is_aux_heat(self) -> bool | None:
            """Return true if aux heater.

            Requires ClimateEntityFeature.AUX_HEAT.
            """
            return True

        async def async_turn_aux_heat_on(self) -> None:
            """Turn auxiliary heater on."""
            await self.hass.async_add_executor_job(self.turn_aux_heat_on)

        async def async_turn_aux_heat_off(self) -> None:
            """Turn auxiliary heater off."""
            await self.hass.async_add_executor_job(self.turn_aux_heat_off)

    # Fake the module is custom component or built in
    MockClimateEntityWithAux.__module__ = module

    climate_entity = MockClimateEntityWithAux(
        name="Testing",
        entity_id="climate.testing",
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
        """Set up test weather platform via config entry."""
        async_add_entities([climate_entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
            partial_manifest=manifest_extra,
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

    assert climate_entity.state == HVACMode.HEAT

    issues = ir.async_get(hass)
    issue = issues.async_get_issue("climate", "deprecated_climate_aux_test")
    assert issue
    assert issue.issue_domain == "test"
    assert issue.issue_id == "deprecated_climate_aux_test"
    assert issue.translation_key == translation_key
    assert (
        issue.translation_placeholders
        == {"platform": "test"} | translation_placeholders_extra
    )

    assert (
        "test::MockClimateEntityWithAux implements the `is_aux_heat` property or uses "
        "the auxiliary  heater methods in a subclass of ClimateEntity which is deprecated "
        f"and will be unsupported from Home Assistant 2024.10. Please {report}"
    ) in caplog.text

    # Assert we only log warning once
    caplog.clear()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            "entity_id": "climate.test",
            "temperature": "25",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert ("implements the `is_aux_heat` property") not in caplog.text


@pytest.mark.parametrize(
    (
        "manifest_extra",
        "translation_key",
        "translation_placeholders_extra",
        "report",
        "module",
    ),
    [
        (
            {"issue_tracker": ISSUE_TRACKER},
            "deprecated_climate_aux_url",
            {"issue_tracker": ISSUE_TRACKER},
            "create a bug report at https://blablabla.com",
            "homeassistant.components.test.climate",
        ),
    ],
)
async def test_no_issue_aux_property_deprecated_for_core(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_flow_fixture: None,
    manifest_extra: dict[str, str],
    translation_key: str,
    translation_placeholders_extra: dict[str, str],
    report: str,
    module: str,
) -> None:
    """Test the no issue on deprecated auxiliary heater attributes for core integrations."""

    class MockClimateEntityWithAux(MockClimateEntity):
        """Mock climate class with mocked aux heater."""

        _attr_supported_features = ClimateEntityFeature.AUX_HEAT

        @property
        def is_aux_heat(self) -> bool | None:
            """Return true if aux heater.

            Requires ClimateEntityFeature.AUX_HEAT.
            """
            return True

        async def async_turn_aux_heat_on(self) -> None:
            """Turn auxiliary heater on."""
            await self.hass.async_add_executor_job(self.turn_aux_heat_on)

        async def async_turn_aux_heat_off(self) -> None:
            """Turn auxiliary heater off."""
            await self.hass.async_add_executor_job(self.turn_aux_heat_off)

    # Fake the module is custom component or built in
    MockClimateEntityWithAux.__module__ = module

    climate_entity = MockClimateEntityWithAux(
        name="Testing",
        entity_id="climate.testing",
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
        """Set up test weather platform via config entry."""
        async_add_entities([climate_entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
            partial_manifest=manifest_extra,
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

    assert climate_entity.state == HVACMode.HEAT

    issues = ir.async_get(hass)
    issue = issues.async_get_issue("climate", "deprecated_climate_aux_test")
    assert not issue

    assert (
        "test::MockClimateEntityWithAux implements the `is_aux_heat` property or uses "
        "the auxiliary  heater methods in a subclass of ClimateEntity which is deprecated "
        f"and will be unsupported from Home Assistant 2024.10. Please {report}"
    ) not in caplog.text


async def test_no_issue_no_aux_property(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_flow_fixture: None,
) -> None:
    """Test the issue is raised on deprecated auxiliary heater attributes."""

    climate_entity = MockClimateEntity(
        name="Testing",
        entity_id="climate.testing",
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
        """Set up test weather platform via config entry."""
        async_add_entities([climate_entity])

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

    assert climate_entity.state == HVACMode.HEAT

    issues = ir.async_get(hass)
    assert len(issues.issues) == 0

    assert (
        "test::MockClimateEntityWithAux implements the `is_aux_heat` property or uses "
        "the auxiliary  heater methods in a subclass of ClimateEntity which is deprecated "
        "and will be unsupported from Home Assistant 2024.10."
    ) not in caplog.text
