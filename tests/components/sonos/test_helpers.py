"""Test the sonos config flow."""

import pytest
from soco.exceptions import SoCoUPnPException

from homeassistant.components.sonos.exception import SonosUpdateError
from homeassistant.components.sonos.helpers import hostname_to_uid, soco_error


async def test_uid_to_hostname() -> None:
    """Test we can convert a hostname to a uid."""
    assert hostname_to_uid("Sonos-347E5C0CF1E3.local.") == "RINCON_347E5C0CF1E301400"
    assert hostname_to_uid("sonos5CAAFDE47AC8.local.") == "RINCON_5CAAFDE47AC801400"

    with pytest.raises(ValueError):
        assert hostname_to_uid("notsonos5CAAFDE47AC8.local.")


def test_soco_error_includes_upnp_code_and_hint() -> None:
    """Test the Sonos wrapper includes UPnP code and a helpful hint."""

    class DummyEntity:
        """Dummy class for exercising the decorator."""

        entity_id = "media_player.test_sonos"

        @soco_error()
        def fail(self) -> None:
            raise SoCoUPnPException("UPnP Error 800 received", "800", "")

    with pytest.raises(SonosUpdateError) as err:
        DummyEntity().fail()

    assert err.value.translation_key == "upnp_call_failed_music_service_unavailable"
    assert err.value.translation_placeholders == {
        "function": "test_soco_error_includes_upnp_code_and_hint.<locals>.DummyEntity.fail",
        "target": "media_player.test_sonos",
        "error": "UPnP Error 800 received",
        "error_code": "800",
    }
