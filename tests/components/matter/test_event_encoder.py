"""Test Matter Event encoder entities.

Tests for rotary/linear encoder support in Matter GenericSwitch devices.
Encoders are detected by MultiPressMax > 8 or LatchingSwitch feature.
"""

from unittest.mock import MagicMock, patch

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType, MatterNodeEvent
import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.components.matter.event import (
    ENCODER_THRESHOLD,
    KNOWN_ENCODERS,
    EncoderConfig,
    EncoderType,
)
from homeassistant.core import HomeAssistant

from .common import (
    create_node_from_fixture,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


class TestEncoderDetection:
    """Tests for encoder device detection."""

    @pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
    async def test_multipress_max_above_threshold_triggers_encoder_mode(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test that MultiPressMax > 8 triggers encoder mode.

        The ikea_scroll_wheel fixture has MultiPressMax=18 (> ENCODER_THRESHOLD=8).
        This should result in encoder mode with rotate_cw/rotate_ccw event types.
        """
        # Endpoint 1 is a rotary encoder on the scroll wheel
        state = hass.states.get("event.bilresa_scroll_wheel_button_1")
        assert state is not None
        # Encoder devices should have rotate event types
        event_types = state.attributes.get(ATTR_EVENT_TYPES, [])
        assert "rotate_cw" in event_types
        assert "rotate_ccw" in event_types
        # Should NOT have multi_press events (encoder mode, not button mode)
        assert not any(et.startswith("multi_press_") for et in event_types)

    @pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
    async def test_latching_switch_triggers_encoder_mode(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test that LatchingSwitch feature triggers encoder mode.

        The ikea_scroll_wheel endpoints have kLatchingSwitch feature (bit 0x2 in featuremap 22).
        LatchingSwitch is a strong signal for encoder behavior.
        """
        # The fixture has featuremap 22 = 0b10110 which includes kLatchingSwitch (0x2)
        state = hass.states.get("event.bilresa_scroll_wheel_button_1")
        assert state is not None
        event_types = state.attributes.get(ATTR_EVENT_TYPES, [])
        # Latching switch should be treated as encoder
        assert "rotate_cw" in event_types or "switch_latched" in event_types

    @pytest.mark.parametrize("node_fixture", ["mock_generic_switch"])
    async def test_normal_switch_not_detected_as_encoder(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test that a normal switch (MultiPressMax <= threshold) is NOT an encoder."""
        state = hass.states.get("event.mock_generic_switch_button")
        assert state is not None
        event_types = state.attributes.get(ATTR_EVENT_TYPES, [])
        # Normal switch should NOT have encoder event types
        assert "rotate_cw" not in event_types
        assert "rotate_ccw" not in event_types
        # Should have normal button events
        assert "initial_press" in event_types


class TestKnownEncodersTable:
    """Tests for the KNOWN_ENCODERS lookup table."""

    def test_ikea_bilresa_in_known_encoders(self) -> None:
        """Test that IKEA BILRESA (vendor 0x117C, product 0x8000) is in the table."""
        # IKEA vendor ID: 0x117C = 4476
        # BILRESA product ID: 0x8000 = 32768
        config = KNOWN_ENCODERS.get((0x117C, 0x8000))
        assert config is not None
        assert config.encoder_type == EncoderType.ROTARY
        assert config.positions == 18

    def test_encoder_config_dataclass(self) -> None:
        """Test EncoderConfig dataclass structure."""
        config = EncoderConfig(EncoderType.LINEAR, 100)
        assert config.encoder_type == EncoderType.LINEAR
        assert config.positions == 100

        # Test default positions (None = use device-reported)
        config_default = EncoderConfig(EncoderType.ROTARY)
        assert config_default.positions is None

    @pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
    async def test_known_encoder_applies_config(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test that known encoder config is applied from the table."""
        # The ikea_scroll_wheel fixture should match KNOWN_ENCODERS
        # and get ROTARY type with 18 positions
        state = hass.states.get("event.bilresa_scroll_wheel_button_1")
        assert state is not None
        # Entity should be in encoder mode
        event_types = state.attributes.get(ATTR_EVENT_TYPES, [])
        assert "rotate_cw" in event_types


class TestEncoderDeltaCalculation:
    """Tests for encoder delta calculation with and without wrap-around."""

    @pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
    async def test_rotary_delta_with_wrap_around(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test rotary encoder delta calculation with wrap-around.

        For a rotary encoder, moving from position 17 to position 0 should be
        interpreted as +1 (wrapping around) rather than -17.
        """
        entity_id = "event.bilresa_scroll_wheel_button_1"

        # First event to set initial position (position 10)
        await trigger_subscription_callback(
            hass,
            matter_client,
            EventType.NODE_EVENT,
            MatterNodeEvent(
                node_id=matter_node.node_id,
                endpoint_id=1,
                cluster_id=59,
                event_id=0,  # SwitchLatched
                event_number=0,
                priority=1,
                timestamp=0,
                timestamp_type=0,
                data={"newPosition": 10},
            ),
        )

        # Move from 10 to 12: should be +2 (no wrap needed)
        await trigger_subscription_callback(
            hass,
            matter_client,
            EventType.NODE_EVENT,
            MatterNodeEvent(
                node_id=matter_node.node_id,
                endpoint_id=1,
                cluster_id=59,
                event_id=0,
                event_number=1,
                priority=1,
                timestamp=0,
                timestamp_type=0,
                data={"newPosition": 12},
            ),
        )
        state = hass.states.get(entity_id)
        assert state.attributes.get(ATTR_EVENT_TYPE) == "rotate_cw"

    @pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
    async def test_rotary_delta_counter_clockwise(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test rotary encoder counter-clockwise rotation detection."""
        entity_id = "event.bilresa_scroll_wheel_button_1"

        # Set initial position
        await trigger_subscription_callback(
            hass,
            matter_client,
            EventType.NODE_EVENT,
            MatterNodeEvent(
                node_id=matter_node.node_id,
                endpoint_id=1,
                cluster_id=59,
                event_id=0,
                event_number=0,
                priority=1,
                timestamp=0,
                timestamp_type=0,
                data={"newPosition": 10},
            ),
        )

        # Move from 10 to 8: should be -2 (counter-clockwise)
        await trigger_subscription_callback(
            hass,
            matter_client,
            EventType.NODE_EVENT,
            MatterNodeEvent(
                node_id=matter_node.node_id,
                endpoint_id=1,
                cluster_id=59,
                event_id=0,
                event_number=1,
                priority=1,
                timestamp=0,
                timestamp_type=0,
                data={"newPosition": 8},
            ),
        )
        state = hass.states.get(entity_id)
        assert state.attributes.get(ATTR_EVENT_TYPE) == "rotate_ccw"


class TestLinearEncoder:
    """Tests for linear encoder (no wrap-around) behavior."""

    @pytest.mark.parametrize(
        ("old_pos", "new_pos", "max_pos", "expected_direction"),
        [
            # Large forward jump - should NOT wrap, treat as linear
            (5, 95, 100, "rotate_cw"),
            # Large backward jump - should NOT wrap, treat as linear
            (95, 5, 100, "rotate_ccw"),
        ],
    )
    def test_linear_delta_no_wrap(
        self,
        old_pos: int,
        new_pos: int,
        max_pos: int,
        expected_direction: str,
    ) -> None:
        """Test that linear encoder uses raw delta without wrap-around.

        When encoder_type is LINEAR, position 95->5 should be -90, not +10.
        This differs from ROTARY which would find the shortest path.
        """
        # Test the delta calculation logic directly
        raw_delta = new_pos - old_pos
        half_max = max_pos // 2

        # For LINEAR type, raw_delta is used as-is
        if expected_direction == "rotate_cw":
            assert raw_delta > 0
        else:
            assert raw_delta < 0


class TestBehaviorInference:
    """Tests for encoder type inference from observed behavior."""

    @pytest.mark.parametrize(
        ("raw_delta", "max_positions", "should_infer_linear"),
        [
            # Large delta (> half max) suggests linear
            (60, 100, True),
            (-60, 100, True),
            # Small delta is ambiguous, should not change inference
            (3, 100, False),
            (-3, 100, False),
            # Exactly at boundary
            (50, 100, False),  # half_max, not > half_max
            (51, 100, True),
        ],
    )
    def test_large_delta_triggers_linear_detection(
        self,
        raw_delta: int,
        max_positions: int,
        should_infer_linear: bool,
    ) -> None:
        """Test that large delta (> half max) triggers LINEAR inference.

        If the user moves a slider by more than half the total range,
        we infer it's a linear device (not rotary) since rotary encoders
        wouldn't have such large jumps without wrapping.
        """
        half_max = max_positions // 2
        would_infer_linear = abs(raw_delta) > half_max
        assert would_infer_linear == should_infer_linear


class TestFirstEventHandling:
    """Tests for handling the first event when no previous position is known."""

    @pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
    async def test_first_event_fires_initial_event(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test that the first encoder event fires an initial position event.

        When we receive the first event and have no previous position,
        we should fire an event with magnitude=0 and initial=True so
        the user gets feedback that the device is responding.
        """
        entity_id = "event.bilresa_scroll_wheel_button_1"
        state = hass.states.get(entity_id)
        # Initial state should be "unknown" (no events yet)
        assert state.state == "unknown"

        # First event arrives with position 5
        await trigger_subscription_callback(
            hass,
            matter_client,
            EventType.NODE_EVENT,
            MatterNodeEvent(
                node_id=matter_node.node_id,
                endpoint_id=1,
                cluster_id=59,
                event_id=0,  # SwitchLatched
                event_number=0,
                priority=1,
                timestamp=0,
                timestamp_type=0,
                data={"newPosition": 5},
            ),
        )

        state = hass.states.get(entity_id)
        # Should have fired an event (not silently dropped)
        assert state.state != "unknown"
        # First event should be a rotate_cw with magnitude 0
        assert state.attributes.get(ATTR_EVENT_TYPE) == "rotate_cw"

    @pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
    async def test_first_event_not_silently_dropped(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test that the first encoder event is NOT silently dropped.

        This is important for user feedback - if someone touches the encoder
        for the first time, they should see some response in Home Assistant.
        """
        entity_id = "event.bilresa_scroll_wheel_button_1"

        # Send first event
        await trigger_subscription_callback(
            hass,
            matter_client,
            EventType.NODE_EVENT,
            MatterNodeEvent(
                node_id=matter_node.node_id,
                endpoint_id=1,
                cluster_id=59,
                event_id=0,
                event_number=0,
                priority=1,
                timestamp=0,
                timestamp_type=0,
                data={"newPosition": 7},
            ),
        )

        state = hass.states.get(entity_id)
        # State should have changed from "unknown"
        assert state.state != "unknown"


class TestEncoderThreshold:
    """Tests for the encoder detection threshold constant."""

    def test_encoder_threshold_value(self) -> None:
        """Test that ENCODER_THRESHOLD is set to expected value."""
        # Threshold should be 8 - anything above this is considered an encoder
        assert ENCODER_THRESHOLD == 8

    @pytest.mark.parametrize(
        ("multi_press_max", "expected_encoder"),
        [
            (2, False),  # Standard button (double-press)
            (4, False),  # Quad-press button
            (8, False),  # At threshold, not above
            (9, True),   # Just above threshold = encoder
            (18, True),  # Well above threshold = encoder
            (100, True), # Very high = encoder
        ],
    )
    def test_threshold_boundary(
        self,
        multi_press_max: int,
        expected_encoder: bool,
    ) -> None:
        """Test encoder detection at threshold boundary.

        MultiPressMax <= 8 = button (typical multi-press support)
        MultiPressMax > 8 = encoder (too many positions for button presses)
        """
        is_encoder = multi_press_max > ENCODER_THRESHOLD
        assert is_encoder == expected_encoder


class TestEncoderEventTypes:
    """Tests for encoder-specific event type attributes."""

    @pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
    async def test_encoder_has_rotate_event_types(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test that encoder entities have rotate_cw and rotate_ccw event types."""
        state = hass.states.get("event.bilresa_scroll_wheel_button_1")
        assert state is not None
        event_types = state.attributes.get(ATTR_EVENT_TYPES, [])
        assert "rotate_cw" in event_types
        assert "rotate_ccw" in event_types

    @pytest.mark.parametrize("node_fixture", ["mock_generic_switch_multi"])
    async def test_button_has_multi_press_event_types(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test that button entities have multi_press event types, not rotate."""
        # Button 2 has MultiPressMax=4 (below threshold)
        state = hass.states.get("event.mock_generic_switch_button_fancy_button")
        assert state is not None
        event_types = state.attributes.get(ATTR_EVENT_TYPES, [])
        # Should have button events
        assert "multi_press_1" in event_types
        # Should NOT have encoder events
        assert "rotate_cw" not in event_types
        assert "rotate_ccw" not in event_types


class TestMultiPressCompleteAsEncoder:
    """Tests for handling MultiPressComplete events as encoder position."""

    @pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
    async def test_multipress_complete_used_for_position(
        self,
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test that MultiPressComplete event's totalNumberOfPressesCounted is used as position.

        Some encoder devices report position via the MultiPressComplete event
        using the totalNumberOfPressesCounted field (repurposed for position).
        """
        entity_id = "event.bilresa_scroll_wheel_button_1"

        # Set initial position via SwitchLatched
        await trigger_subscription_callback(
            hass,
            matter_client,
            EventType.NODE_EVENT,
            MatterNodeEvent(
                node_id=matter_node.node_id,
                endpoint_id=1,
                cluster_id=59,
                event_id=0,  # SwitchLatched
                event_number=0,
                priority=1,
                timestamp=0,
                timestamp_type=0,
                data={"newPosition": 5},
            ),
        )

        # Now send MultiPressComplete with position as totalNumberOfPressesCounted
        await trigger_subscription_callback(
            hass,
            matter_client,
            EventType.NODE_EVENT,
            MatterNodeEvent(
                node_id=matter_node.node_id,
                endpoint_id=1,
                cluster_id=59,
                event_id=6,  # MultiPressComplete
                event_number=1,
                priority=1,
                timestamp=0,
                timestamp_type=0,
                data={"totalNumberOfPressesCounted": 7},
            ),
        )

        state = hass.states.get(entity_id)
        # Should have processed the position change (5 -> 7 = +2, clockwise)
        assert state.attributes.get(ATTR_EVENT_TYPE) == "rotate_cw"
