"""Checks for basic helper utils."""
from homeassistant.components.homekit_controller.utils import unique_id_to_iids


def test_unique_id_to_iids():
    """Check that unique_id_to_iids is safe against different invalid ids."""
    assert unique_id_to_iids("pairingid_1_2_3") == (1, 2, 3)
    assert unique_id_to_iids("pairingid_1_2") == (1, 2, None)
    assert unique_id_to_iids("pairingid_1") == (1, None, None)

    assert unique_id_to_iids("pairingid") is None
    assert unique_id_to_iids("pairingid_1_2_3_4") is None
    assert unique_id_to_iids("pairingid_a") is None
    assert unique_id_to_iids("pairingid_1_a") is None
    assert unique_id_to_iids("pairingid_1_2_a") is None
