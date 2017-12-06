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

# This is a pure-Python implementation of the AES algorithm and AES common
# modes of operation.

# See: https://en.wikipedia.org/wiki/Advanced_Encryption_Standard
# See: https://en.wikipedia.org/wiki/Block_cipher_mode_of_operation


# Supported key sizes:
#   128-bit
#   192-bit
#   256-bit


# Supported modes of operation:
#   ECB - Electronic Codebook
#   CBC - Cipher-Block Chaining
#   CFB - Cipher Feedback
#   OFB - Output Feedback
#   CTR - Counter

# See the README.md for API details and general information.

# Also useful, PyCrypto, a crypto library implemented in C with Python bindings:
# https://www.dlitz.net/software/pycrypto/


VERSION = [1, 3, 0]

from .aes import AES, AESModeOfOperationCTR, AESModeOfOperationCBC, AESModeOfOperationCFB, AESModeOfOperationECB, AESModeOfOperationOFB, AESModesOfOperation, Counter
from .blockfeeder import decrypt_stream, Decrypter, encrypt_stream, Encrypter
from .blockfeeder import PADDING_NONE, PADDING_DEFAULT
