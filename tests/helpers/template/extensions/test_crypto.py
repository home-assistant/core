"""Test cryptographic hash functions for Home Assistant templates."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from tests.helpers.template.helpers import render


def test_md5(hass: HomeAssistant) -> None:
    """Test the md5 function and filter."""
    assert (
        render(hass, "{{ md5('Home Assistant') }}")
        == "3d15e5c102c3413d0337393c3287e006"
    )

    assert (
        render(hass, "{{ 'Home Assistant' | md5 }}")
        == "3d15e5c102c3413d0337393c3287e006"
    )


def test_sha1(hass: HomeAssistant) -> None:
    """Test the sha1 function and filter."""
    assert (
        render(hass, "{{ sha1('Home Assistant') }}")
        == "c8fd3bb19b94312664faa619af7729bdbf6e9f8a"
    )

    assert (
        render(hass, "{{ 'Home Assistant' | sha1 }}")
        == "c8fd3bb19b94312664faa619af7729bdbf6e9f8a"
    )


def test_sha256(hass: HomeAssistant) -> None:
    """Test the sha256 function and filter."""
    assert (
        render(hass, "{{ sha256('Home Assistant') }}")
        == "2a366abb0cd47f51f3725bf0fb7ebcb4fefa6e20f4971e25fe2bb8da8145ce2b"
    )

    assert (
        render(hass, "{{ 'Home Assistant' | sha256 }}")
        == "2a366abb0cd47f51f3725bf0fb7ebcb4fefa6e20f4971e25fe2bb8da8145ce2b"
    )


def test_sha512(hass: HomeAssistant) -> None:
    """Test the sha512 function and filter."""
    assert (
        render(hass, "{{ sha512('Home Assistant') }}")
        == "9e3c2cdd1fbab0037378d37e1baf8a3a4bf92c54b56ad1d459deee30ccbb2acbebd7a3614552ea08992ad27dedeb7b4c5473525ba90cb73dbe8b9ec5f69295bb"
    )

    assert (
        render(hass, "{{ 'Home Assistant' | sha512 }}")
        == "9e3c2cdd1fbab0037378d37e1baf8a3a4bf92c54b56ad1d459deee30ccbb2acbebd7a3614552ea08992ad27dedeb7b4c5473525ba90cb73dbe8b9ec5f69295bb"
    )
