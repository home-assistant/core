"""Test HassDict and custom HassKey types."""

from homeassistant.util.hass_dict import HassDict, HassEntryKey, HassKey


def test_key_comparison() -> None:
    """Test key comparison with itself and string keys."""

    str_key = "custom-key"
    key = HassKey[int](str_key)
    other_key = HassKey[str]("other-key")

    entry_key = HassEntryKey[int](str_key)
    other_entry_key = HassEntryKey[str]("other-key")

    assert key == str_key
    assert key != other_key
    assert key != 2

    assert entry_key == str_key
    assert entry_key != other_entry_key
    assert entry_key != 2

    # Only compare name attribute, HassKey(<name>) == HassEntryKey(<name>)
    assert key == entry_key


def test_hass_dict_access() -> None:
    """Test keys with the same name all access the same value in HassDict."""

    data = HassDict()
    str_key = "custom-key"
    key = HassKey[int](str_key)
    other_key = HassKey[str]("other-key")

    entry_key = HassEntryKey[int](str_key)
    other_entry_key = HassEntryKey[str]("other-key")

    data[str_key] = True
    assert data.get(key) is True
    assert data.get(other_key) is None

    assert data.get(entry_key) is True  # type: ignore[comparison-overlap]
    assert data.get(other_entry_key) is None

    data[key] = False
    assert data[str_key] is False
