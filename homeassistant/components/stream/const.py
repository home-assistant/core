"""Constants for Stream component."""
DOMAIN = 'stream'

ATTR_ENDPOINTS = 'endpoints'
ATTR_STREAMS = 'streams'
ATTR_KEEPALIVE = 'keepalive'

OUTPUT_FORMATS = ['hls']

FORMAT_CONTENT_TYPE = {
    'hls': 'application/vnd.apple.mpegurl'
}

AUDIO_SAMPLE_RATE = 44100
