"""Constants for Remote Now Playing.

The wire keys here are one half of a cross-repository protocol: the Home Assistant iOS app decodes
them with `RemoteMediaSessionAttributes`, so every name and casing below is copied from the Swift
`CodingKeys` rather than chosen. See `tests/components/mobile_app/remote_media/test_mapper.py`,
which asserts the encoded shape against that contract.
"""

# Webhook commands the iOS app calls. Named in `RemoteMediaSessionRegistration` and
# `RemoteMediaSessionDismissal` on the client side.
WEBHOOK_TYPE_TOKEN = "remote_media_session_token"
WEBHOOK_TYPE_DISMISSED = "remote_media_session_dismissed"

# Webhook payload keys, from the Swift `CodingKeys` of those two types.
# `entity_id` is `homeassistant.const.ATTR_ENTITY_ID`, imported where it is used.
ATTR_SESSION_ID = "session_id"
ATTR_GENERATION = "generation"
ATTR_GENERATION_SEQUENCE = "generation_sequence"
ATTR_SERVER_ID_KEY = "server_id"
ATTR_PUSH_TOKEN = "push_token"
ATTR_SCHEMA_VERSION = "schema_version"

# The only schema the iOS app emits (`RemoteMediaSessionRegistration.currentSchemaVersion`).
SUPPORTED_SCHEMA_VERSIONS = frozenset({1})

# Bounds for the values a client may send. A session identifier and a generation are short
# machine-generated strings, and the update token was 80 bytes on the platform it was measured on;
# the ceilings are generous multiples so a future change does not need a Core release.
MAX_SESSION_ID_LENGTH = 512
MAX_GENERATION_LENGTH = 128
MAX_SERVER_ID_LENGTH = 128
MAX_PUSH_TOKEN_LENGTH = 512

# The largest Follow sequence that survives the trip back to the device. The push relay is a Node
# process, so a JSON number there is a double: a larger value would reach the phone rounded, and
# two relationships that round to the same value would be indistinguishable. Matches Swift
# `RemoteMediaFollowLifetime.maximumSequence`.
MAX_GENERATION_SEQUENCE = 9_007_199_254_740_991

# Relay request keys, from the committed `functions/now-playing.js` contract.
ATTR_NOW_PLAYING = "now_playing"
ATTR_NOW_PLAYING_TOKEN = "now_playing_token"
ATTR_EVENT = "event"
ATTR_TIMESTAMP = "timestamp"
ATTR_ATTRIBUTES = "attributes"
ATTR_REGISTRATION_INFO = "registration_info"

EVENT_UPDATE = "update"
EVENT_END = "end"

# Attributes keys, from Swift `RemoteMediaSessionAttributes.CodingKeys`. camelCase here and
# snake_case on the webhook, deliberately: this side is Swift `Codable`, that side is the
# `mobile_app` payload convention. `id` and `state` are `homeassistant.const`'s.
ATTR_SNAPSHOT = "snapshot"
ATTR_WIRE_GENERATION_SEQUENCE = "generationSequence"

# Snapshot keys, from Swift `RemoteMediaSnapshot.CodingKeys`. camelCase, deliberately.
ATTR_SELECTION = "selection"
ATTR_SERVER_ID = "serverId"
ATTR_WIRE_ENTITY_ID = "entityId"
ATTR_DEVICE_NAME = "deviceName"
ATTR_DEVICE_CLASS = "deviceClass"
ATTR_TITLE = "title"
ATTR_ARTIST = "artist"
ATTR_ALBUM = "album"
ATTR_CONTENT_ID = "contentId"
ATTR_DURATION = "duration"
ATTR_POSITION = "position"
ATTR_POSITION_UPDATED_AT_UNIX = "positionUpdatedAtUnix"
ATTR_ARTWORK = "artwork"
# The key inside `artwork`. Matches Swift `RemoteMediaArtworkDescriptor.CodingKeys.url`.
ATTR_ARTWORK_URL = "url"
ATTR_VOLUME = "volume"
ATTR_IS_MUTED = "isMuted"
ATTR_FEATURES = "features"

# How long several state events are allowed to settle into one push. Integrations emit sequences
# like `playing A` -> `idle` (blank) -> `playing B` within milliseconds, and the card should learn
# the outcome rather than each contradictory step.
COALESCE_SECONDS = 0.2

# How far a reported position may differ from where ordinary playback would have reached before it
# counts as a seek rather than as progress. Generous enough to absorb integration rounding and
# clock skew, tight enough to catch the usual 10, 15 and 30 second skips.
SEEK_TOLERANCE_SECONDS = 3.0

# Smallest volume movement worth a push, on the 0..1 scale the wire uses.
VOLUME_CHANGE_THRESHOLD = 0.02

# How long to stay quiet after the relay reports a condition that will not change on its own: a
# deployment that does not serve this app, a credential fault, an oversized payload. Without this
# every state change of a playing media player would log the same failure.
CONFIGURATION_BACKOFF_SECONDS = 3600

# How long to stay quiet after being told to slow down.
RATE_LIMIT_BACKOFF_SECONDS = 900

# Relay `errorType` values, from `functions/now-playing.js` and `functions/handlers.js`.
ERROR_INVALID_TOKEN = "InvalidToken"
ERROR_UNSUPPORTED_APP = "UnsupportedApp"
ERROR_TOPIC_MISMATCH = "TopicMismatch"
ERROR_PROVIDER_AUTH = "ProviderAuth"
ERROR_PAYLOAD_TOO_LARGE = "PayloadTooLarge"
ERROR_RATE_LIMITED = "RateLimited"
ERROR_APNS_RATE_LIMITED = "ApnsRateLimited"
ERROR_APNS_UNAVAILABLE = "ApnsUnavailable"
ERROR_NOT_CONFIGURED = "NowPlayingNotConfigured"

# How long to wait before offering an undelivered update again, doubling up to the maximum while it
# keeps failing. A retry of one specific update rather than a poll: armed only while a snapshot is
# owed, and stopped as soon as one is delivered or superseded. It exists because "the next state
# change will carry it" is not true of an integration that emits an event only when something
# changes — there, a track change that failed to send waits until the user touches the speaker.
RETRY_BACKOFF_SECONDS = 30
MAXIMUM_RETRY_BACKOFF_SECONDS = 900
