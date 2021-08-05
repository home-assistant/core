"""Constants for Stream component."""
DOMAIN = "stream"

ATTR_ENDPOINTS = "endpoints"
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
TARGET_SEGMENT_DURATION = 2.0  # Each segment is about this many seconds
TARGET_PART_DURATION = 1.0
SEGMENT_DURATION_ADJUSTER = 0.1  # Used to avoid missing keyframe boundaries
# Each segment is at least this many seconds
MIN_SEGMENT_DURATION = TARGET_SEGMENT_DURATION - SEGMENT_DURATION_ADJUSTER

# Number of target durations to start before the end of the playlist.
# 1.5 should put us in the middle of the second to last segment even with
# variable keyframe intervals.
EXT_X_START = 1.5

PACKETS_TO_WAIT_FOR_AUDIO = 20  # Some streams have an audio stream with no audio
MAX_TIMESTAMP_GAP = 10000  # seconds - anything from 10 to 50000 is probably reasonable

MAX_MISSING_DTS = 6  # Number of packets missing DTS to allow
SOURCE_TIMEOUT = 30  # Timeout for reading stream source

STREAM_RESTART_INCREMENT = 10  # Increase wait_timeout by this amount each retry
STREAM_RESTART_RESET_TIME = 300  # Reset wait_timeout after this many seconds
