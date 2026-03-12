"""Adapter to convert OH protocol events to pysiaalarm SIAEvent objects."""

from __future__ import annotations

import copy
from datetime import datetime
import logging

from osbornehoffman import MessageType, OHEvent
from pysiaalarm import SIAEvent
from pysiaalarm.utils import SIA_CODES, MessageTypes

_LOGGER = logging.getLogger(__name__)


def oh_event_to_sia_event(oh_event: OHEvent) -> SIAEvent:
    """Convert an OHEvent to a pysiaalarm SIAEvent for HA entity consumption.

    This creates a SIAEvent with the fields needed by the SIA integration's
    entity layer (alarm_control_panel, binary_sensor). We bypass
    SIAEvent.__post_init__ since OH events are already parsed and decrypted.
    """
    code = oh_event.code
    msg_type = oh_event.message_type

    # Map OH MessageType to pysiaalarm MessageTypes
    match msg_type:
        case MessageType.HB_V1 | MessageType.HB_V2:
            sia_msg_type = MessageTypes.NULL
        case MessageType.SIA:
            sia_msg_type = MessageTypes.SIADCS
        case MessageType.CID:
            sia_msg_type = MessageTypes.ADMCID
        case _:
            sia_msg_type = MessageTypes.OH

    # Build the SIAEvent using __new__ to bypass __post_init__ parsing.
    #
    # pysiaalarm compatibility notes (tested against pysiaalarm 3.2.2):
    # - SIAEvent is a @dataclass; we set all public fields and five private
    #   parse-guard flags (_content_parsed, _encrypted_content_decrypted,
    #   _adm_parsed, _sia_added, _xdata_parsed) to prevent __post_init__
    #   from re-parsing already-decoded OH data.
    # - msg_crc == calc_crc ensures the valid_message property returns True.
    # - SIA_CODES dict and MessageTypes enum must remain compatible.
    # - If pysiaalarm adds/removes SIAEvent fields or renames parse flags,
    #   this adapter will need updating.
    event = SIAEvent.__new__(SIAEvent)

    # Main frame fields
    event.full_message = None
    event.msg_crc = "0000"
    event.calc_crc = "0000"  # Match msg_crc so valid_message returns True
    event.length = None
    event.encrypted = False
    event.message_type = sia_msg_type
    event.receiver = f"R{oh_event.receiver or '0000'}"
    event.line = f"L{oh_event.line or '0000'}"
    event.account = oh_event.effective_account
    event.sequence = oh_event.sequence or "0000"

    # Content fields (not needed for OH, already parsed)
    event.content = None
    event.encrypted_content = None

    # Parsed event fields
    event.ti = None
    event.id = str(oh_event.panel_id) if oh_event.panel_id is not None else None
    event.ri = oh_event.ri
    event.code = code
    event.message = oh_event.text
    event.x_data = None
    event.timestamp = _parse_timestamp(oh_event.timestamp)

    # ADM-CID fields
    event.event_qualifier = oh_event.qualifier
    event.event_type = oh_event.event_code
    event.partition = oh_event.area

    # Metadata
    event.extended_data = None
    event.sia_account = None
    event.sia_code = copy.copy(SIA_CODES.get(code)) if code else None

    # Parse flags (prevent re-parsing)
    event._content_parsed = True  # noqa: SLF001
    event._encrypted_content_decrypted = True  # noqa: SLF001
    event._adm_parsed = True  # noqa: SLF001
    event._sia_added = True  # noqa: SLF001
    event._xdata_parsed = True  # noqa: SLF001

    return event


def _parse_timestamp(ts: datetime | str | None) -> datetime | str | None:
    """Parse timestamp to datetime, passing through unparseable strings as-is."""
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return ts
    return None
