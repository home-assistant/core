"""Tests for stips_iru1 constants and helpers."""

from homeassistant.components.stips_iru1 import const


class TestRemoteType:
    """Tests for remote type helpers."""

    def test_is_protocol_ac() -> None:
        """Test protocol AC detection."""
        assert const.is_protocol_ac("AC") is True
        assert const.is_protocol_ac("ac") is True
        assert const.is_protocol_ac(" AC ") is True
        assert const.is_protocol_ac("LearnedAc") is False
        assert const.is_protocol_ac("TV") is False
        assert const.is_protocol_ac("") is False
        assert const.is_protocol_ac(None) is False

    def test_is_learned_ac() -> None:
        """Test learned AC detection."""
        assert const.is_learned_ac("LearnedAc") is True
        assert const.is_learned_ac("learnedac") is True
        assert const.is_learned_ac(" LearnedAc ") is True
        assert const.is_learned_ac("AC") is False
        assert const.is_learned_ac("LearnedTV") is False
        assert const.is_learned_ac("") is False
        assert const.is_learned_ac(None) is False

    def test_remote_uses_signal_buttons() -> None:
        """Test signal button remote detection."""
        # LearnedAc should NOT have signal buttons (uses climate only)
        assert const.remote_uses_signal_buttons("LearnedAc") is False

        # AC should NOT have signal buttons (uses protocol only)
        assert const.remote_uses_signal_buttons("AC") is False

        # LearnedTV should have signal buttons
        assert const.remote_uses_signal_buttons("LearnedTV") is True
        assert const.remote_uses_signal_buttons("LearnedFan") is True

        # Unknown types should have signal buttons
        assert const.remote_uses_signal_buttons("Unknown") is True
        assert const.remote_uses_signal_buttons("") is True
        assert const.remote_uses_signal_buttons(None) is True

    def test_normalize_remote_type() -> None:
        """Test remote type normalization."""
        assert const.normalize_remote_type("AC") == "ac"
        assert const.normalize_remote_type("LearnedAc") == "learnedac"
        assert const.normalize_remote_type(" AC ") == "ac"
        assert const.normalize_remote_type("Learned TV") == "learnedtv"
        assert const.normalize_remote_type("") == ""
        assert const.normalize_remote_type(None) == ""
