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
def channels():
    """Return a mock of channels."""

    def channel(name, chan_id):
        ch = mock.MagicMock()
        ch.name = name
        ch.generic_id = chan_id
        return ch

    return [channel("level", "channel_0x0008"), channel("on_off", "channel_0x0006")]


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
        (registries.MatchRule(manufacturer="no match"), False),
        (registries.MatchRule(manufacturer=MANUFACTURER), True),
        (registries.MatchRule(model=MODEL), True),
        (registries.MatchRule(model="no match"), False),
        # match everything
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
                manufacturer=MANUFACTURER,
                model=MODEL,
            ),
            True,
        ),
    ],
)
def test_registry_matching(rule, matched, zha_device, channels):
    """Test empty rule matching."""
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
            registries.MatchRule(channel_names={"on_off", "level"}, model="no match"),
            True,
        ),
        (
            registries.MatchRule(
                channel_names={"on_off", "level"},
                model="no match",
                manufacturer="no match",
            ),
            True,
        ),
        (
            registries.MatchRule(
                channel_names={"on_off", "level"},
                model="no match",
                manufacturer=MANUFACTURER,
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
                model="mo match",
            ),
            False,
        ),
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008", "channel_0x0009"},
                model=MODEL,
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
        (registries.MatchRule(manufacturer="no match"), False),
        (registries.MatchRule(manufacturer=MANUFACTURER), True),
        (registries.MatchRule(model=MODEL), True),
        (registries.MatchRule(model="no match"), False),
        # match everything
        (
            registries.MatchRule(
                generic_ids={"channel_0x0006", "channel_0x0008"},
                channel_names={"on_off", "level"},
                manufacturer=MANUFACTURER,
                model=MODEL,
            ),
            True,
        ),
    ],
)
def test_registry_loose_matching(rule, matched, zha_device, channels):
    """Test loose rule matching."""
    reg = registries.ZHAEntityRegistry()
    assert reg._loose_matched(zha_device, channels, rule) is matched
