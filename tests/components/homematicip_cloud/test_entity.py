"""Unit tests for HomematicipGenericEntity naming helpers."""

from types import SimpleNamespace

import pytest

from homeassistant.components.homematicip_cloud.entity import HomematicipGenericEntity


def _make_entity(
    *,
    device_label: str,
    channels: dict[int, str],
    channel: int,
    is_multi_channel: bool,
    post: str | None = None,
) -> HomematicipGenericEntity:
    """Build a HomematicipGenericEntity bypassing __init__ for unit testing.

    Only the attributes read by _setup_entity_name() are populated.
    """
    entity = HomematicipGenericEntity.__new__(HomematicipGenericEntity)
    entity._device = SimpleNamespace(
        label=device_label,
        functionalChannels={
            idx: SimpleNamespace(label=label, index=idx)
            for idx, label in channels.items()
        },
    )
    entity._post = post
    entity._channel = channel
    entity._channel_real_index = channel
    entity._is_multi_channel = is_multi_channel
    entity.functional_channel = entity._device.functionalChannels.get(channel)
    entity._attr_name = None
    return entity


@pytest.mark.parametrize(
    ("device_label", "channel_label"),
    [
        ("Thermostat EG Wohnzimmer", "Thermostat EG Wohnzimmer"),
        ("Thermostat EG Wohnzimmer", "Thermostat EG Wohnzimmer "),
        ("Thermostat EG Wohnzimmer ", "Thermostat EG Wohnzimmer "),
    ],
    ids=["exact-match", "trailing-space-on-channel", "trailing-space-on-both"],
)
def test_multi_channel_label_equals_device_label_leaves_name_unset(
    device_label: str, channel_label: str
) -> None:
    """When channel label equals device label, _attr_name must stay None.

    Otherwise HA composes "{device_name} {entity_name}" and the user sees the
    label duplicated, e.g. "Thermostat EG Wohnzimmer Thermostat EG Wohnzimmer".
    """
    entity = _make_entity(
        device_label=device_label,
        channels={3: channel_label, 1: "primary"},
        channel=3,
        is_multi_channel=True,
    )
    entity._setup_entity_name()
    assert entity._attr_name is None


def test_multi_channel_label_extends_device_label_keeps_suffix() -> None:
    """When channel label starts with device label + suffix, keep the suffix."""
    entity = _make_entity(
        device_label="Licht Flur",
        channels={5: "Licht Flur 5"},
        channel=5,
        is_multi_channel=True,
    )
    entity._setup_entity_name()
    assert entity._attr_name == "5"


def test_multi_channel_label_unrelated_to_device_label_uses_full_label() -> None:
    """When channel label does not start with device label, use it verbatim."""
    entity = _make_entity(
        device_label="DRS8-4",
        channels={2: "Flur OG Lampe"},
        channel=2,
        is_multi_channel=True,
    )
    entity._setup_entity_name()
    assert entity._attr_name == "Flur OG Lampe"


def test_primary_entity_with_channel_1_label_equals_device_label_unset() -> None:
    """Non-multi-channel entity on device whose ch1 label equals device label.

    Same duplication risk as the multi-channel case; same fix.
    """
    entity = _make_entity(
        device_label="Thermostat EG Wohnzimmer",
        channels={1: "Thermostat EG Wohnzimmer ", 2: "other"},
        channel=2,  # non-multi-channel entity sits on some channel
        is_multi_channel=False,
    )
    entity._setup_entity_name()
    assert entity._attr_name is None


def test_post_suffix_capitalised() -> None:
    """Post suffix becomes the entity name with first letter uppercased."""
    entity = _make_entity(
        device_label="Bewegungsmelder Küche",
        channels={1: "primary"},
        channel=1,
        is_multi_channel=False,
        post="battery",
    )
    entity._setup_entity_name()
    assert entity._attr_name == "Battery"
