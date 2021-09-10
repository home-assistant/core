"""Cryptography for communicators."""


class Crypto:
    """Cryptography."""

    __xor4 = bytearray(4)
    __xor_in_cnt = 0
    __xor_out_cnt = 0

    def crypt_init(self, password: int):
        """Cryptography initialization."""
        if (password is None) or (password < 0):
            password = 0
        self.__xor4 = bytearray(4)
        self.__xor_in_cnt = 0
        self.__xor_out_cnt = 0
        self.__convert_cipher(int(password))

    def crypt_out_reset(self):
        """Reset of cryptography."""
        self.__xor_out_cnt = 0

    def __convert_cipher(self, password: int):
        password_converted = self.__convert_password(password)
        for i in range(0, 4):
            self.__xor4[3 - i] = 0x1F & password_converted
            password_converted >>= 5

    def code_string(self, input_str: str) -> str:
        """Encode string."""
        output = ""
        for byte in bytes(input_str, "ascii"):
            # code one byte
            if (byte & 0x80) != 0:
                byte = byte ^ self.__xor4[self.__xor_in_cnt] & 0x7F
            elif (byte & 0x60) != 0:
                byte = byte ^ self.__xor4[self.__xor_in_cnt] & 0x1F
            if (byte == 13) or (byte == 10):
                self.__xor_in_cnt = 0
            else:
                self.__xor_in_cnt = self.__xor_in_cnt + 1 & 3
            # add encoded byte to output string
            output = output + chr(byte)
        return output

    def decode_string(self, input_str: str) -> str:
        """Decode string."""
        output = ""
        for byte in bytes(input_str, "ascii"):
            # code one byte
            if (byte & 0x80) != 0:
                byte = byte ^ self.__xor4[self.__xor_out_cnt] & 0x7F
            elif (byte & 0x60) != 0:
                byte = byte ^ self.__xor4[self.__xor_out_cnt] & 0x1F
            if (byte == 13) or (byte == 10):
                self.__xor_out_cnt = 0
            else:
                self.__xor_out_cnt = self.__xor_out_cnt + 1 & 3
            # add encoded byte to output string
            output = output + chr(byte)
        return output

    @staticmethod
    def __convert_password(password: int) -> int:
        if password == 0:
            return 0
        p_byte = [0] * 4
        for i in range(4):
            p_byte[i] = password & 0x1F
            password >>= 5
            if p_byte[i] < 3:
                p_byte[i] = p_byte[i] + (9 + 4 * i)
        for i in range(4):
            password <<= 5
            password |= p_byte[3 - i]
        return password
