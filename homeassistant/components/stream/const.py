"""Constants for Stream component."""
DOMAIN = "stream"

ATTR_ENDPOINTS = "endpoints"
ATTR_STREAMS = "streams"

OUTPUT_FORMATS = ["hls"]

FORMAT_CONTENT_TYPE = {"hls": "application/vnd.apple.mpegurl"}

OUTPUT_IDLE_TIMEOUT = 300  # Idle timeout due to inactivity

NUM_PLAYLIST_SEGMENTS = 3  # Number of segments to use in HLS playlist
MAX_SEGMENTS = 4  # Max number of segments to keep around
MIN_SEGMENT_DURATION = 1.5  # Each segment is at least this many seconds

PACKETS_TO_WAIT_FOR_AUDIO = 20  # Some streams have an audio stream with no audio
MAX_TIMESTAMP_GAP = 10000  # seconds - anything from 10 to 50000 is probably reasonable

MAX_MISSING_DTS = 6  # Number of packets missing DTS to allow
STREAM_TIMEOUT = 30  # Timeout for reading stream

STREAM_RESTART_INCREMENT = 10  # Increase wait_timeout by this amount each retry
STREAM_RESTART_RESET_TIME = 300  # Reset wait_timeout after this many seconds
