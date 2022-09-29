"""Constants for Stream component."""
DOMAIN = "stream"

ATTR_ENDPOINTS = "endpoints"
ATTR_SETTINGS = "settings"
ATTR_STREAMS = "streams"

HLS_PROVIDER = "hls"
RECORDER_PROVIDER = "recorder"

OUTPUT_FORMATS = [HLS_PROVIDER]

SEGMENT_CONTAINER_FORMAT = "mp4"  # format for segments
RECORDER_CONTAINER_FORMAT = "mp4"  # format for recorder output
AUDIO_CODECS = {"aac", "mp3"}

FORMAT_CONTENT_TYPE = {HLS_PROVIDER: "application/vnd.apple.mpegurl"}

OUTPUT_IDLE_TIMEOUT = 300  # Idle timeout due to inactivity

NUM_PLAYLIST_SEGMENTS = 3  # Number of segments to use in HLS playlist
MAX_SEGMENTS = 5  # Max number of segments to keep around
TARGET_SEGMENT_DURATION_NON_LL_HLS = 2.0  # Each segment is about this many seconds
SEGMENT_DURATION_ADJUSTER = 0.1  # Used to avoid missing keyframe boundaries
# Number of target durations to start before the end of the playlist.
# 1.5 should put us in the middle of the second to last segment even with
# variable keyframe intervals.
EXT_X_START_NON_LL_HLS = 1.5
# Number of part durations to start before the end of the playlist with LL-HLS
EXT_X_START_LL_HLS = 2


PACKETS_TO_WAIT_FOR_AUDIO = 20  # Some streams have an audio stream with no audio
MAX_TIMESTAMP_GAP = 10000  # seconds - anything from 10 to 50000 is probably reasonable

MAX_MISSING_DTS = 6  # Number of packets missing DTS to allow
SOURCE_TIMEOUT = 30  # Timeout for reading stream source

STREAM_RESTART_INCREMENT = 10  # Increase wait_timeout by this amount each retry
STREAM_RESTART_RESET_TIME = 300  # Reset wait_timeout after this many seconds

CONF_LL_HLS = "ll_hls"
CONF_PART_DURATION = "part_duration"
CONF_SEGMENT_DURATION = "segment_duration"

CONF_PREFER_TCP = "prefer_tcp"
CONF_RTSP_TRANSPORT = "rtsp_transport"
# The first dict entry below may be used as the default when populating options
RTSP_TRANSPORTS = {
    "tcp": "TCP",
    "udp": "UDP",
    "udp_multicast": "UDP Multicast",
    "http": "HTTP",
}
CONF_USE_WALLCLOCK_AS_TIMESTAMPS = "use_wallclock_as_timestamps"
CONF_EXTRA_PART_WAIT_TIME = "extra_part_wait_time"
