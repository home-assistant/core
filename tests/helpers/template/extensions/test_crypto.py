"""Test cryptographic hash functions for Home Assistant templates."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template


def test_md5(hass: HomeAssistant) -> None:
    """Test the md5 function and filter."""
    assert (
        template.Template("{{ md5('Home Assistant') }}", hass).async_render()
        == "3d15e5c102c3413d0337393c3287e006"
    )

    assert (
        template.Template("{{ 'Home Assistant' | md5 }}", hass).async_render()
        == "3d15e5c102c3413d0337393c3287e006"
    )


def test_sha1(hass: HomeAssistant) -> None:
    """Test the sha1 function and filter."""
    assert (
        template.Template("{{ sha1('Home Assistant') }}", hass).async_render()
        == "c8fd3bb19b94312664faa619af7729bdbf6e9f8a"
    )

    assert (
        template.Template("{{ 'Home Assistant' | sha1 }}", hass).async_render()
        == "c8fd3bb19b94312664faa619af7729bdbf6e9f8a"
    )


def test_sha256(hass: HomeAssistant) -> None:
    """Test the sha256 function and filter."""
    assert (
        template.Template("{{ sha256('Home Assistant') }}", hass).async_render()
        == "2a366abb0cd47f51f3725bf0fb7ebcb4fefa6e20f4971e25fe2bb8da8145ce2b"
    )

    assert (
        template.Template("{{ 'Home Assistant' | sha256 }}", hass).async_render()
        == "2a366abb0cd47f51f3725bf0fb7ebcb4fefa6e20f4971e25fe2bb8da8145ce2b"
    )


def test_sha512(hass: HomeAssistant) -> None:
    """Test the sha512 function and filter."""
    assert (
        template.Template("{{ sha512('Home Assistant') }}", hass).async_render()
        == "9e3c2cdd1fbab0037378d37e1baf8a3a4bf92c54b56ad1d459deee30ccbb2acbebd7a3614552ea08992ad27dedeb7b4c5473525ba90cb73dbe8b9ec5f69295bb"
    )

    assert (
        template.Template("{{ 'Home Assistant' | sha512 }}", hass).async_render()
        == "9e3c2cdd1fbab0037378d37e1baf8a3a4bf92c54b56ad1d459deee30ccbb2acbebd7a3614552ea08992ad27dedeb7b4c5473525ba90cb73dbe8b9ec5f69295bb"
    )
