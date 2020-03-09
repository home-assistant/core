"""Test ZHA registries."""
from unittest import mock

import pytest

import homeassistant.components.zha.core.registries as registries

MANUFACTURER = "mock manufacturer"
MODEL = "mock model"


@pytest.fixture
def zha_device():
    """Return a mock of ZHA device."""
    dev = mock.MagicMock()
    dev.manufacturer = MANUFACTURER
    dev.model = MODEL
    return dev


@pytest.fixture
def channels(channel):
    """Return a mock of channels."""

    return [channel("level", 8), channel("on_off", 6)]


@pytest.mark.parametrize(
    "rule, matched",
    [
        (registries.MatchRule(), False),
        (registries.MatchRule(channel_names={"level"}), True),
        (registries.MatchRule(channel_names={"level", "no match"}), False),
        (registries.MatchRule(channel_names={"on_off"}), True),
        (registries.MatchRule(channel_names={"on_off", "no match"}), False),
        (registries.MatchRule(channel_names={"on_off", "level"}), True),
        (registries.MatchRule(channel_names={"on_off", "level", "no match"}), False),
        # test generic_id matching
        (registries.MatchRule(generic_ids={"channel_0x0006"}), True),
        (registries.MatchRule(generic_ids={"channel_0x0008"}), True),
        (registries.MatchRule(generic_ids={"channel_0x0006", "channel_0x0008"}), True),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008", "channel_0x0009"}
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
            ),
            True,
        ),
        # manufacturer matching
        (registries.MatchRule(manufacturers="no match"), False),
        (registries.MatchRule(manufacturers=MANUFACTURER), True),
        (registries.MatchRule(models=MODEL), True),
        (registries.MatchRule(models="no match"), False),
        # match everything
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
                manufacturers=MANUFACTURER,
                models=MODEL,
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", manufacturers={"random manuf", MANUFACTURER}
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", manufacturers={"random manuf", "Another manuf"}
            ),
            False,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", manufacturers=lambda x: x == MANUFACTURER
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", manufacturers=lambda x: x != MANUFACTURER
            ),
            False,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", models={"random model", MODEL}
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names="on_off", models={"random model", "Another model"}
            ),
            False,
        ),
        (
            registries.MatchRule(channel_names="on_off", models=lambda x: x == MODEL),
            True,
        ),
        (
            registries.MatchRule(channel_names="on_off", models=lambda x: x != MODEL),
            False,
        ),
    ],
)
def test_registry_matching(rule, matched, zha_device, channels):
    """Test strict rule matching."""
    reg = registries.ZHAEntityRegistry()
    assert reg._strict_matched(zha_device, channels, rule) is matched


@pytest.mark.parametrize(
    "rule, matched",
    [
        (registries.MatchRule(), False),
        (registries.MatchRule(channel_names={"level"}), True),
        (registries.MatchRule(channel_names={"level", "no match"}), False),
        (registries.MatchRule(channel_names={"on_off"}), True),
        (registries.MatchRule(channel_names={"on_off", "no match"}), False),
        (registries.MatchRule(channel_names={"on_off", "level"}), True),
        (registries.MatchRule(channel_names={"on_off", "level", "no match"}), False),
        (
            registries.MatchRule(channel_names={"on_off", "level"}, models="no match"),
            True,
        ),
        (
            registries.MatchRule(
                channel_names={"on_off", "level"},
                models="no match",
                manufacturers="no match",
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names={"on_off", "level"},
                models="no match",
                manufacturers=MANUFACTURER,
            ),
            True,
        ),
        # test generic_id matching
        (registries.MatchRule(generic_ids={"channel_0x0006"}), True),
        (registries.MatchRule(generic_ids={"channel_0x0008"}), True),
        (registries.MatchRule(generic_ids={"channel_0x0006", "channel_0x0008"}), True),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008", "channel_0x0009"}
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008", "channel_0x0009"},
                models="mo match",
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008", "channel_0x0009"},
                models=MODEL,
            ),
            True,
        ),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
            ),
            True,
        ),
        # manufacturer matching
        (registries.MatchRule(manufacturers="no match"), False),
        (registries.MatchRule(manufacturers=MANUFACTURER), True),
        (registries.MatchRule(models=MODEL), True),
        (registries.MatchRule(models="no match"), False),
        # match everything
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
                manufacturers=MANUFACTURER,
                models=MODEL,
            ),
            True,
        ),
    ],
)
def test_registry_loose_matching(rule, matched, zha_device, channels):
    """Test loose rule matching."""
    reg = registries.ZHAEntityRegistry()
    assert reg._loose_matched(zha_device, channels, rule) is matched
