"""Tests for the vendored Electra API client."""

from homeassistant.components.electrasmart.pyelectra.device import ElectraAirConditioner


def test_device_token_optional_when_missing() -> None:
    """A device record without a ``deviceToken`` must not crash parsing.

    The Electra ``GET_DEVICES`` response may omit ``deviceToken`` for some
    units; upstream pyElectra 1.2.4 hard-crashed on the missing key, which
    prevented the whole integration from setting up (GH issue #183846).
    """
    record = {
        "id": "123",
        "name": "Living Room AC",
        "regdate": "2024-01-01",
        "model": "Electra A/C",
        "mac": "a8032ab12345",
        "sn": "SN123",
        "manufactor": "Electra",
        "deviceTypeName": "A/C",
        "status": "ok",
        # no "deviceToken" key on purpose
    }

    device = ElectraAirConditioner(record)

    assert device.id == "123"
    assert device.token == ""
