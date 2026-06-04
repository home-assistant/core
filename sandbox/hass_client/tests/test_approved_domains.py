"""Tests for the :class:`ApprovedDomains` gate."""

from hass_client.approved_domains import ApprovedDomains


def test_add_and_approves() -> None:
    """An added domain is approved (case-insensitively)."""
    approved = ApprovedDomains()
    approved.add("Hue")

    assert approved.approves("hue")
    assert approved.approves("HUE")
    assert "hue" in approved
    assert not approved.approves("philips")


def test_remove_respects_refcount() -> None:
    """Two adds need two removes before approval drops."""
    approved = ApprovedDomains()
    approved.add("zha")
    approved.add("zha")
    approved.remove("zha")

    assert approved.approves("zha")

    approved.remove("zha")

    assert not approved.approves("zha")


def test_initial_seed() -> None:
    """The initial iterable seeds the approved set."""
    approved = ApprovedDomains(["mqtt", "light"])

    assert approved.approves("mqtt")
    assert approved.approves("light")


def test_approves_event_matches_domain_prefix() -> None:
    """``<domain>_*`` events approve; bare types and unrelated do not."""
    approved = ApprovedDomains(["zha", "device_tracker"])

    assert approved.approves_event("zha_event")
    assert approved.approves_event("device_tracker_see")
    # No underscore — never matches.
    assert not approved.approves_event("started")
    # Domain not approved.
    assert not approved.approves_event("hue_event")
    # Prefix-only collision (mqtt vs mqtt_message_received): unapproved
    # domain doesn't sneak through just because it shares a prefix.
    assert not approved.approves_event("mqtt_message_received")


def test_remove_below_zero_is_safe() -> None:
    """Removing a never-added domain is a no-op."""
    approved = ApprovedDomains()
    approved.remove("never")

    assert not approved.approves("never")
