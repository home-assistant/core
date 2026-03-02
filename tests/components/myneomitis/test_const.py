"""Tests for the MyNeomitis const module."""

from homeassistant.components.myneomitis.const import (
    CONF_USER_ID,
    DOMAIN,
    PRESET_BY_CODE,
    PRESET_BY_KEY,
    PRESET_MODE_MAP,
    PRESET_MODE_MAP_RELAIS,
    PRESET_MODE_MAP_UFH,
    PRESET_MODE_MODELS,
    PRESET_MODE_SELECT_EXTRAS,
    REVERSE_PRESET_MODE_MAP,
    REVERSE_PRESET_MODE_MAP_RELAIS,
    REVERSE_PRESET_MODE_MAP_UFH,
    Preset,
)


def test_domain_and_conf_user_id() -> None:
    """Basic constants are set to expected values."""
    assert DOMAIN == "myneomitis"
    assert CONF_USER_ID == "user_id"


def test_preset_key_property() -> None:
    """Preset.key returns the text key for each member."""
    assert Preset.COMFORT.key == "comfort"
    assert Preset.ECO.key == "eco"
    assert Preset.ANTIFROST.key == "antifrost"
    assert Preset.STANDBY.key == "standby"
    assert Preset.BOOST.key == "boost"
    assert Preset.SETPOINT.key == "setpoint"
    assert Preset.COMFORT_PLUS.key == "comfort_plus"
    assert Preset.AUTO.key == "auto"


def test_preset_code_property() -> None:
    """Preset.code returns the numeric code for each member."""
    assert Preset.COMFORT.code == 1
    assert Preset.ECO.code == 2
    assert Preset.ANTIFROST.code == 3
    assert Preset.STANDBY.code == 4
    assert Preset.BOOST.code == 6
    assert Preset.SETPOINT.code == 8
    assert Preset.COMFORT_PLUS.code == 20
    assert Preset.AUTO.code == 60


def test_preset_str() -> None:
    """str(Preset) returns the key string."""
    assert str(Preset.COMFORT) == "comfort"
    assert str(Preset.ECO) == "eco"
    assert str(Preset.AUTO) == "auto"


def test_preset_by_key_lookup() -> None:
    """PRESET_BY_KEY maps each key string to the correct Preset."""
    assert PRESET_BY_KEY["comfort"] is Preset.COMFORT
    assert PRESET_BY_KEY["eco"] is Preset.ECO
    assert PRESET_BY_KEY["auto"] is Preset.AUTO
    assert len(PRESET_BY_KEY) == len(Preset)


def test_preset_by_code_lookup() -> None:
    """PRESET_BY_CODE maps each numeric code to the correct Preset."""
    assert PRESET_BY_CODE[1] is Preset.COMFORT
    assert PRESET_BY_CODE[60] is Preset.AUTO
    assert len(PRESET_BY_CODE) == len(Preset)


def test_preset_mode_map_roundtrip() -> None:
    """PRESET_MODE_MAP and REVERSE_PRESET_MODE_MAP are inverses of each other."""
    for key, code in PRESET_MODE_MAP.items():
        assert REVERSE_PRESET_MODE_MAP[code] == key


def test_preset_mode_models_contains_expected_keys() -> None:
    """PRESET_MODE_MODELS contains entries for known device models."""
    expected_models = {"EV30", "ECTRL", "ESTAT", "RSS-ECTRL", "NTD", "ETRV"}
    assert expected_models <= set(PRESET_MODE_MODELS.keys())
    for model, presets in PRESET_MODE_MODELS.items():
        for p in presets:
            assert p in PRESET_BY_KEY, f"{p!r} not a valid preset key (model={model})"


def test_preset_mode_map_relais_roundtrip() -> None:
    """PRESET_MODE_MAP_RELAIS and REVERSE_PRESET_MODE_MAP_RELAIS are inverses."""
    for key, code in PRESET_MODE_MAP_RELAIS.items():
        assert REVERSE_PRESET_MODE_MAP_RELAIS[code] == key


def test_preset_mode_map_ufh_roundtrip() -> None:
    """PRESET_MODE_MAP_UFH and REVERSE_PRESET_MODE_MAP_UFH are inverses."""
    for key, code in PRESET_MODE_MAP_UFH.items():
        assert REVERSE_PRESET_MODE_MAP_UFH[code] == key


def test_preset_mode_select_extras_values() -> None:
    """PRESET_MODE_SELECT_EXTRAS contains fixed codes."""
    assert PRESET_MODE_SELECT_EXTRAS["eco_1"] == 40
    assert PRESET_MODE_SELECT_EXTRAS["eco_2"] == 41
