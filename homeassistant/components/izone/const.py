"""Constants used by the izone component."""

from datetime import timedelta

from pizone import VerifyFailure

DOMAIN = "izone"

TIMEOUT_DISCOVERY = 5
DISCOVERY_IDLE_SECONDS = 4 * TIMEOUT_DISCOVERY
# Match legacy pizone DISCOVERY_SLEEP (~5 min) for new-device hunt cadence.
DISCOVERY_SCAN_INTERVAL = timedelta(minutes=5)

VERIFY_FAILURE_KEYS = {
    VerifyFailure.UNRESOLVED: "host_unresolved",
    VerifyFailure.NO_REPLY: "cannot_connect",
    VerifyFailure.UNREADABLE: "unreadable_reply",
    VerifyFailure.OTHER_UID: "other_controller",
}
