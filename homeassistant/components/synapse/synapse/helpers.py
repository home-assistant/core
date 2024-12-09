import binascii
import gzip
import io
import json

from .const import SynapseApplication

def hex_to_object(hex_str: str) -> SynapseApplication:
    """
    Consume a gzipped json string, return an object.
    Can be any object but will only be used for this single return type
    """
    compressed_data = binascii.unhexlify(hex_str)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed_data)) as f:
        json_str = f.read().decode('utf-8')
    return json.loads(json_str)
