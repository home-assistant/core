"""Constants for tests imap integration."""

DATE_HEADER1 = b"Date: Fri, 24 Mar 2023 13:52:00 +0100\r\n"
DATE_HEADER2 = b"Date: Fri, 24 Mar 2023 13:52:00 +0100 (CET)\r\n"
DATE_HEADER3 = b"Date: 24 Mar 2023 13:52:00 +0100\r\n"
DATE_HEADER_INVALID1 = b"2023-03-27T13:52:00 +0100\r\n"
DATE_HEADER_INVALID2 = b"Date: 2023-03-27T13:52:00 +0100\r\n"
DATE_HEADER_INVALID3 = b"Date: Fri, 2023-03-27T13:52:00 +0100\r\n"

TEST_MESSAGE_HEADERS1 = (
    b"Return-Path: <john.doe@example.com>\r\nDelivered-To: notify@example.com\r\n"
    b"Received: from beta.example.com\r\n\tby beta with LMTP\r\n\t"
    b"id eLp2M/GcHWQTLxQAho4UZQ\r\n\t(envelope-from <john.doe@example.com>)\r\n\t"
    b"for <notify@example.com>; Fri, 24 Mar 2023 13:52:01 +0100\r\n"
    b"Received: from localhost (localhost [127.0.0.1])\r\n\t"
    b"by beta.example.com (Postfix) with ESMTP id D0FFA61425\r\n\t"
    b"for <notify@example.com>; Fri, 24 Mar 2023 13:52:01 +0100 (CET)\r\n"
)
TEST_MESSAGE_HEADERS2 = (
    b"To: notify@example.com\r\n"
    b"From: John Doe <john.doe@example.com>\r\n"
    b"Subject: Test subject\r\n"
    b"Message-ID: <N753P9hLvLw3lYGan11ji9WggPjxtLSpKvFOYgdnE@example.com>\r\n"
    b"MIME-Version: 1.0\r\n"
)

TEST_MULTIPART_HEADER = (
    b'Content-Type: multipart/related;\r\n\tboundary="Mark=_100584970350292485166"'
)

TEST_MESSAGE_HEADERS3 = b""

TEST_MESSAGE = TEST_MESSAGE_HEADERS1 + DATE_HEADER1 + TEST_MESSAGE_HEADERS2

TEST_MESSAGE_MULTIPART = (
    TEST_MESSAGE_HEADERS1 + DATE_HEADER1 + TEST_MESSAGE_HEADERS2 + TEST_MULTIPART_HEADER
)

TEST_MESSAGE_NO_SUBJECT_TO_FROM = (
    TEST_MESSAGE_HEADERS1 + DATE_HEADER1 + TEST_MESSAGE_HEADERS3
)
TEST_MESSAGE_ALT = TEST_MESSAGE_HEADERS1 + DATE_HEADER2 + TEST_MESSAGE_HEADERS2
TEST_INVALID_DATE1 = (
    TEST_MESSAGE_HEADERS1 + DATE_HEADER_INVALID1 + TEST_MESSAGE_HEADERS2
)
TEST_INVALID_DATE2 = (
    TEST_MESSAGE_HEADERS1 + DATE_HEADER_INVALID2 + TEST_MESSAGE_HEADERS2
)
TEST_INVALID_DATE3 = (
    TEST_MESSAGE_HEADERS1 + DATE_HEADER_INVALID3 + TEST_MESSAGE_HEADERS2
)

TEST_CONTENT_TEXT_BARE = b"\r\nTest body\r\n\r\n"

TEST_CONTENT_BINARY = b"Content-Type: application/binary\r\n\r\nTest body\r\n"

TEST_CONTENT_TEXT_PLAIN = (
    b'Content-Type: text/plain; charset="utf-8"\r\n'
    b"Content-Transfer-Encoding: 7bit\r\n\r\nTest body\r\n"
)

TEST_CONTENT_TEXT_PLAIN_EMPTY = (
    b'Content-Type: text/plain; charset="utf-8"\r\n'
    b"Content-Transfer-Encoding: 7bit\r\n\r\n  \r\n"
)

TEST_CONTENT_TEXT_BASE64 = (
    b'Content-Type: text/plain; charset="utf-8"\r\n'
    b"Content-Transfer-Encoding: base64\r\n\r\nVGVzdCBib2R5\r\n"
)

TEST_CONTENT_TEXT_BASE64_INVALID = (
    b'Content-Type: text/plain; charset="utf-8"\r\n'
    b"Content-Transfer-Encoding: base64\r\n\r\nVGVzdCBib2R5invalid\r\n"
)
TEST_BADLY_ENCODED_CONTENT = "VGVzdCBib2R5invalid\r\n"

TEST_CONTENT_TEXT_OTHER = (
    b"Content-Type: text/other; charset=UTF-8\r\n"
    b"Content-Transfer-Encoding: 7bit\r\n\r\nTest body\r\n"
)

TEST_CONTENT_HTML = (
    b"Content-Type: text/html; charset=UTF-8\r\n"
    b"Content-Transfer-Encoding: 7bit\r\n"
    b"\r\n"
    b"<html>\r\n"
    b"  <head>\r\n"
    b'    <meta http-equiv="content-type" content="text/html; charset=UTF-8">\r\n'
    b"  </head>\r\n"
    b"  <body>\r\n"
    b"    <p>Test body<br>\r\n"
    b"    </p>\r\n"
    b"  </body>\r\n"
    b"</html>\r\n"
    b"\r\n"
)
TEST_CONTENT_HTML_BASE64 = (
    b"Content-Type: text/html; charset=UTF-8\r\n"
    b"Content-Transfer-Encoding: base64\r\n\r\n"
    b"PGh0bWw+CiAgICA8aGVhZD48bWV0YSBodHRwLWVxdW"
    b"l2PSJjb250ZW50LXR5cGUiIGNvbnRlbnQ9InRleHQvaHRtbDsgY2hhcnNldD1VVEYtOCI+PC9oZWFkPgog"
    b"CAgPGJvZHk+CiAgICAgIDxwPlRlc3QgYm9keTxicj48L3A+CiAgICA8L2JvZHk+CjwvaHRtbD4=\r\n"
)


TEST_CONTENT_MULTIPART = (
    b"\r\nThis is a multi-part message in MIME format.\r\n"
    b"\r\n--Mark=_100584970350292485166\r\n"
    + TEST_CONTENT_TEXT_PLAIN
    + b"\r\n--Mark=_100584970350292485166\r\n"
    + TEST_CONTENT_HTML
    + b"\r\n--Mark=_100584970350292485166--\r\n"
)

TEST_CONTENT_MULTIPART_EMPTY_PLAIN = (
    b"\r\nThis is a multi-part message in MIME format.\r\n"
    b"\r\n--Mark=_100584970350292485166\r\n"
    + TEST_CONTENT_TEXT_PLAIN_EMPTY
    + b"\r\n--Mark=_100584970350292485166\r\n"
    + TEST_CONTENT_HTML
    + b"\r\n--Mark=_100584970350292485166--\r\n"
)

TEST_CONTENT_MULTIPART_BASE64 = (
    b"\r\nThis is a multi-part message in MIME format.\r\n"
    b"\r\n--Mark=_100584970350292485166\r\n"
    + TEST_CONTENT_TEXT_BASE64
    + b"\r\n--Mark=_100584970350292485166\r\n"
    + TEST_CONTENT_HTML_BASE64
    + b"\r\n--Mark=_100584970350292485166--\r\n"
)

TEST_CONTENT_MULTIPART_BASE64_INVALID = (
    b"\r\nThis is a multi-part message in MIME format.\r\n"
    b"\r\n--Mark=_100584970350292485166\r\n"
    + TEST_CONTENT_TEXT_BASE64_INVALID
    + b"\r\n--Mark=_100584970350292485166\r\n"
    + TEST_CONTENT_HTML_BASE64
    + b"\r\n--Mark=_100584970350292485166--\r\n"
)

EMPTY_SEARCH_RESPONSE = ("OK", [b"", b"Search completed (0.0001 + 0.000 secs)."])
BAD_RESPONSE = ("BAD", [b"", b"Unexpected error"])

TEST_SEARCH_RESPONSE = ("OK", [b"1", b"Search completed (0.0001 + 0.000 secs)."])

TEST_FETCH_RESPONSE_TEXT_BARE = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE + TEST_CONTENT_TEXT_BARE)).encode("utf-8")
        + b"}",
        bytearray(TEST_MESSAGE + TEST_CONTENT_TEXT_BARE),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

TEST_FETCH_RESPONSE_TEXT_PLAIN = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE + TEST_CONTENT_TEXT_PLAIN)).encode("utf-8")
        + b"}",
        bytearray(TEST_MESSAGE + TEST_CONTENT_TEXT_PLAIN),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

TEST_FETCH_RESPONSE_TEXT_PLAIN_EMPTY = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE + TEST_CONTENT_TEXT_PLAIN_EMPTY)).encode("utf-8")
        + b"}",
        bytearray(TEST_MESSAGE + TEST_CONTENT_TEXT_PLAIN_EMPTY),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

TEST_FETCH_RESPONSE_TEXT_PLAIN_ALT = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE_ALT + TEST_CONTENT_TEXT_PLAIN)).encode("utf-8")
        + b"}",
        bytearray(TEST_MESSAGE_ALT + TEST_CONTENT_TEXT_PLAIN),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

TEST_FETCH_RESPONSE_INVALID_DATE1 = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_INVALID_DATE1 + TEST_CONTENT_TEXT_PLAIN)).encode("utf-8")
        + b"}",
        bytearray(TEST_INVALID_DATE1 + TEST_CONTENT_TEXT_PLAIN),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)
TEST_FETCH_RESPONSE_INVALID_DATE2 = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_INVALID_DATE2 + TEST_CONTENT_TEXT_PLAIN)).encode("utf-8")
        + b"}",
        bytearray(TEST_INVALID_DATE2 + TEST_CONTENT_TEXT_PLAIN),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)
TEST_FETCH_RESPONSE_INVALID_DATE3 = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_INVALID_DATE3 + TEST_CONTENT_TEXT_PLAIN)).encode("utf-8")
        + b"}",
        bytearray(TEST_INVALID_DATE3 + TEST_CONTENT_TEXT_PLAIN),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)


TEST_FETCH_RESPONSE_TEXT_OTHER = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE + TEST_CONTENT_TEXT_OTHER)).encode("utf-8")
        + b"}",
        bytearray(TEST_MESSAGE + TEST_CONTENT_TEXT_OTHER),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

TEST_FETCH_RESPONSE_BINARY = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE + TEST_CONTENT_BINARY)).encode("utf-8")
        + b"}",
        bytearray(TEST_MESSAGE + TEST_CONTENT_BINARY),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

TEST_FETCH_RESPONSE_HTML = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE + TEST_CONTENT_HTML)).encode("utf-8")
        + b"}",
        bytearray(TEST_MESSAGE + TEST_CONTENT_HTML),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

TEST_FETCH_RESPONSE_MULTIPART = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE_MULTIPART + TEST_CONTENT_MULTIPART)).encode("utf-8")
        + b"}",
        bytearray(TEST_MESSAGE_MULTIPART + TEST_CONTENT_MULTIPART),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)
TEST_FETCH_RESPONSE_MULTIPART_EMPTY_PLAIN = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE_MULTIPART + TEST_CONTENT_MULTIPART_EMPTY_PLAIN)).encode(
            "utf-8"
        )
        + b"}",
        bytearray(TEST_MESSAGE_MULTIPART + TEST_CONTENT_MULTIPART_EMPTY_PLAIN),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)
TEST_FETCH_RESPONSE_MULTIPART_BASE64 = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE_MULTIPART + TEST_CONTENT_MULTIPART_BASE64)).encode(
            "utf-8"
        )
        + b"}",
        bytearray(TEST_MESSAGE_MULTIPART + TEST_CONTENT_MULTIPART_BASE64),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

TEST_FETCH_RESPONSE_MULTIPART_BASE64_INVALID = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(
            len(TEST_MESSAGE_MULTIPART + TEST_CONTENT_MULTIPART_BASE64_INVALID)
        ).encode("utf-8")
        + b"}",
        bytearray(TEST_MESSAGE_MULTIPART + TEST_CONTENT_MULTIPART_BASE64_INVALID),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

TEST_FETCH_RESPONSE_NO_SUBJECT_TO_FROM = (
    "OK",
    [
        b"1 FETCH (BODY[] {"
        + str(len(TEST_MESSAGE_NO_SUBJECT_TO_FROM + TEST_CONTENT_TEXT_PLAIN)).encode(
            "utf-8"
        )
        + b"}",
        bytearray(TEST_MESSAGE_NO_SUBJECT_TO_FROM + TEST_CONTENT_TEXT_PLAIN),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

RESPONSE_BAD = ("BAD", [])
