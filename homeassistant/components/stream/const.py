"""Constants for Stream component."""
DOMAIN = "stream"

ATTR_HLS_ENDPOINT = "hls_endpoint"
ATTR_STREAMS = "streams"

HLS_OUTPUT = "hls"
OUTPUT_FORMATS = [HLS_OUTPUT]
OUTPUT_CONTAINER_FORMAT = "mp4"
OUTPUT_VIDEO_CODECS = {"hevc", "h264"}
OUTPUT_AUDIO_CODECS = {"aac", "mp3"}

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
