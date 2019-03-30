"""Constants for Stream component."""
DOMAIN = 'stream'

CONF_STREAM_SOURCE = 'stream_source'
CONF_LOOKBACK = 'lookback'
CONF_DURATION = 'duration'
CONF_BASE_URL = 'base_url'

ATTR_ENDPOINTS = 'endpoints'
ATTR_STREAMS = 'streams'
ATTR_KEEPALIVE = 'keepalive'

SERVICE_RECORD = 'record'

OUTPUT_FORMATS = ['hls']

FORMAT_CONTENT_TYPE = {
    'hls': 'application/vnd.apple.mpegurl'
}

AUDIO_SAMPLE_RATE = 44100
