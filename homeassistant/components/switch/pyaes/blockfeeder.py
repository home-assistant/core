# The MIT License (MIT)
#
# Copyright (c) 2014 Richard Moore
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


from .aes import AESBlockModeOfOperation, AESSegmentModeOfOperation, AESStreamModeOfOperation
from .util import append_PKCS7_padding, strip_PKCS7_padding, to_bufferable


# First we inject three functions to each of the modes of operations
#
#    _can_consume(size)
#       - Given a size, determine how many bytes could be consumed in
#         a single call to either the decrypt or encrypt method
#
#    _final_encrypt(data, padding = PADDING_DEFAULT)
#       - call and return encrypt on this (last) chunk of data,
#         padding as necessary; this will always be at least 16
#         bytes unless the total incoming input was less than 16
#         bytes
#
#    _final_decrypt(data, padding = PADDING_DEFAULT)
#       - same as _final_encrypt except for decrypt, for
#         stripping off padding
#

PADDING_NONE       = 'none'
PADDING_DEFAULT    = 'default'

# @TODO: Ciphertext stealing and explicit PKCS#7
# PADDING_CIPHERTEXT_STEALING
# PADDING_PKCS7

# ECB and CBC are block-only ciphers

def _block_can_consume(self, size):
    if size >= 16: return 16
    return 0

# After padding, we may have more than one block
def _block_final_encrypt(self, data, padding = PADDING_DEFAULT):
    if padding == PADDING_DEFAULT:
        data = append_PKCS7_padding(data)

    elif padding == PADDING_NONE:
        if len(data) != 16:
            raise Exception('invalid data length for final block')
    else:
        raise Exception('invalid padding option')

    if len(data) == 32:
        return self.encrypt(data[:16]) + self.encrypt(data[16:])

    return self.encrypt(data)


def _block_final_decrypt(self, data, padding = PADDING_DEFAULT):
    if padding == PADDING_DEFAULT:
        return strip_PKCS7_padding(self.decrypt(data))

    if padding == PADDING_NONE:
        if len(data) != 16:
            raise Exception('invalid data length for final block')
        return self.decrypt(data)

    raise Exception('invalid padding option')

AESBlockModeOfOperation._can_consume = _block_can_consume
AESBlockModeOfOperation._final_encrypt = _block_final_encrypt
AESBlockModeOfOperation._final_decrypt = _block_final_decrypt



# CFB is a segment cipher

def _segment_can_consume(self, size):
    return self.segment_bytes * int(size // self.segment_bytes)

# CFB can handle a non-segment-sized block at the end using the remaining cipherblock
def _segment_final_encrypt(self, data, padding = PADDING_DEFAULT):
    if padding != PADDING_DEFAULT:
        raise Exception('invalid padding option')

    faux_padding = (chr(0) * (self.segment_bytes - (len(data) % self.segment_bytes)))
    padded = data + to_bufferable(faux_padding)
    return self.encrypt(padded)[:len(data)]

# CFB can handle a non-segment-sized block at the end using the remaining cipherblock
def _segment_final_decrypt(self, data, padding = PADDING_DEFAULT):
    if padding != PADDING_DEFAULT:
        raise Exception('invalid padding option')

    faux_padding = (chr(0) * (self.segment_bytes - (len(data) % self.segment_bytes)))
    padded = data + to_bufferable(faux_padding)
    return self.decrypt(padded)[:len(data)]

AESSegmentModeOfOperation._can_consume = _segment_can_consume
AESSegmentModeOfOperation._final_encrypt = _segment_final_encrypt
AESSegmentModeOfOperation._final_decrypt = _segment_final_decrypt



# OFB and CTR are stream ciphers

def _stream_can_consume(self, size):
    return size

def _stream_final_encrypt(self, data, padding = PADDING_DEFAULT):
    if padding not in [PADDING_NONE, PADDING_DEFAULT]:
        raise Exception('invalid padding option')

    return self.encrypt(data)

def _stream_final_decrypt(self, data, padding = PADDING_DEFAULT):
    if padding not in [PADDING_NONE, PADDING_DEFAULT]:
        raise Exception('invalid padding option')

    return self.decrypt(data)

AESStreamModeOfOperation._can_consume = _stream_can_consume
AESStreamModeOfOperation._final_encrypt = _stream_final_encrypt
AESStreamModeOfOperation._final_decrypt = _stream_final_decrypt



class BlockFeeder(object):
    '''The super-class for objects to handle chunking a stream of bytes
       into the appropriate block size for the underlying mode of operation
       and applying (or stripping) padding, as necessary.'''

    def __init__(self, mode, feed, final, padding = PADDING_DEFAULT):
        self._mode = mode
        self._feed = feed
        self._final = final
        self._buffer = to_bufferable("")
        self._padding = padding

    def feed(self, data = None):
        '''Provide bytes to encrypt (or decrypt), returning any bytes
           possible from this or any previous calls to feed.

           Call with None or an empty string to flush the mode of
           operation and return any final bytes; no further calls to
           feed may be made.'''

        if self._buffer is None:
            raise ValueError('already finished feeder')

        # Finalize; process the spare bytes we were keeping
        if data is None:
            result = self._final(self._buffer, self._padding)
            self._buffer = None
            return result

        self._buffer += to_bufferable(data)

        # We keep 16 bytes around so we can determine padding
        result = to_bufferable('')
        while len(self._buffer) > 16:
            can_consume = self._mode._can_consume(len(self._buffer) - 16)
            if can_consume == 0: break
            result += self._feed(self._buffer[:can_consume])
            self._buffer = self._buffer[can_consume:]

        return result


class Encrypter(BlockFeeder):
    'Accepts bytes of plaintext and returns encrypted ciphertext.'

    def __init__(self, mode, padding = PADDING_DEFAULT):
        BlockFeeder.__init__(self, mode, mode.encrypt, mode._final_encrypt, padding)


class Decrypter(BlockFeeder):
    'Accepts bytes of ciphertext and returns decrypted plaintext.'

    def __init__(self, mode, padding = PADDING_DEFAULT):
        BlockFeeder.__init__(self, mode, mode.decrypt, mode._final_decrypt, padding)


# 8kb blocks
BLOCK_SIZE = (1 << 13)

def _feed_stream(feeder, in_stream, out_stream, block_size = BLOCK_SIZE):
    'Uses feeder to read and convert from in_stream and write to out_stream.'

    while True:
        chunk = in_stream.read(block_size)
        if not chunk:
            break
        converted = feeder.feed(chunk)
        out_stream.write(converted)
    converted = feeder.feed()
    out_stream.write(converted)


def encrypt_stream(mode, in_stream, out_stream, block_size = BLOCK_SIZE, padding = PADDING_DEFAULT):
    'Encrypts a stream of bytes from in_stream to out_stream using mode.'

    encrypter = Encrypter(mode, padding = padding)
    _feed_stream(encrypter, in_stream, out_stream, block_size)


def decrypt_stream(mode, in_stream, out_stream, block_size = BLOCK_SIZE, padding = PADDING_DEFAULT):
    'Decrypts a stream of bytes from in_stream to out_stream using mode.'

    decrypter = Decrypter(mode, padding = padding)
    _feed_stream(decrypter, in_stream, out_stream, block_size)
