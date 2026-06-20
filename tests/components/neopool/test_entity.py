"""Tests for the NeoPool base entity helpers."""

from homeassistant.components.neopool.entity import NeoPoolEntity


def test_slugify_empty_returns_empty_string() -> None:
    """slugify('') falls into the early return for falsy input."""
    assert NeoPoolEntity.slugify("") == ""


def test_slugify_strips_mbf_par_prefix() -> None:
    """Slugify drops the leading 'mbf_' and 'par_' prefix segments."""
    assert NeoPoolEntity.slugify("MBF_PAR_FILT_MODE") == "filt_mode"


def test_format_modules_no_data_returns_unknown() -> None:
    """An empty data dict (MBF_PAR_MODEL missing) yields 'Unknown'."""
    assert NeoPoolEntity._format_modules({}) == "Unknown"


def test_format_modules_uses_lib_decoded_key() -> None:
    """The lib-provided ``installed_modules`` list maps to UI labels."""
    data = {"installed_modules": ["ionization", "hydrolysis", "uv_lamp", "salinity"]}
    assert (
        NeoPoolEntity._format_modules(data)
        == "Ionization, Hydro/Electrolysis, UV Lamp, Salinity"
    )


def test_format_modules_falls_back_to_raw_register() -> None:
    """If ``installed_modules`` is missing, decode MBF_PAR_MODEL on the fly."""
    data = {"MBF_PAR_MODEL": 0x0001 | 0x0002 | 0x0004 | 0x0008}
    rendered = NeoPoolEntity._format_modules(data)
    for label in ("Ionization", "Hydro/Electrolysis", "UV Lamp", "Salinity"):
        assert label in rendered


def test_format_modules_zero_register_returns_none_label() -> None:
    """MBF_PAR_MODEL=0 (no modules detected) yields the 'None' label."""
    assert NeoPoolEntity._format_modules({"MBF_PAR_MODEL": 0}) == "None"


def test_format_modules_unknown_module_falls_back_to_raw_name() -> None:
    """A future module name from the lib is rendered as-is."""
    data = {"installed_modules": ["future_module"]}
    assert NeoPoolEntity._format_modules(data) == "future_module"
