"""Constants for tests imap integration."""

TEST_MESSAGE = (
    b"Return-Path: <john.doe@example.com>\r\nDelivered-To: notify@example.com\r\n"
    b"Received: from beta.example.com\r\n\tby beta with LMTP\r\n\t"
    b"id eLp2M/GcHWQTLxQAho4UZQ\r\n\t(envelope-from <john.doe@example.com>)\r\n\t"
    b"for <notify@example.com>; Fri, 24 Mar 2023 13:52:01 +0100\r\n"
    b"Received: from localhost (localhost [127.0.0.1])\r\n\t"
    b"by beta.example.com (Postfix) with ESMTP id D0FFA61425\r\n\t"
    b"for <notify@example.com>; Fri, 24 Mar 2023 13:52:01 +0100 (CET)\r\n"
    b"Received: from beta.example.com ([192.168.200.137])\r\n\t"
    b"by localhost (beta.example.com [127.0.0.1]) (amavisd-new, port 12345)\r\n\t"
    b"with ESMTP id ycTJJEDpDgm0 for <notify@example.com>;\r\n\t"
    b"Fri, 24 Mar 2023 13:52:01 +0100 (CET)\r\n"
    b"Received: from [IPV6:2001:db8::ed28:3645:f874:395f] "
    b"(demo [IPv6:2001:db8::ed28:3645:f874:395f])\r\n\t(using TLSv1.3 with cipher "
    b"TLS_AES_256_GCM_SHA384 (256/256 bits)\r\n\t key-exchange ECDHE (P-384) "
    b"server-signature RSA-PSS (2048 bits))\r\n\t(No client certificate requested)\r\n\t"
    b"by beta.example.com (Postfix) with ESMTPSA id B942E609BE\r\n\t"
    b"for <notify@example.com>; Fri, 24 Mar 2023 13:52:01 +0100 (CET)\r\n\t"
    b"h=Message-ID:Date:MIME-Version:To:From:Subject:Content-Type:\r\n\t "
    b"Message-ID: <48eca8bb-0551-446b-d8c5-02157f38cca7@example.com>\r\nDate: Fri, 24 Mar 2023 13:52:00 +0100\r\nMIME-Version: 1.0\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101\r\n Thunderbird/102.9.0\r\n"
    b"To: notify@example.com\r\n"
    b"From: John Doe <john.doe@example.com>\r\n"
    b"Subject: Test subject\r\n"
    b"Content-Type: text/plain; charset=UTF-8; format=flowed\r\n"
    b"Content-Transfer-Encoding: 7bit\r\n\r\nTest body\r\n\r\n"
)

EMPTY_SEARCH_RESPONSE = ("OK", [b"", b"Search completed (0.0001 + 0.000 secs)."])
BAD_SEARCH_RESPONSE = ("BAD", [b"", b"Unexpected error"])

TEST_SEARCH_RESPONSE = ("OK", [b"1", b"Search completed (0.0001 + 0.000 secs)."])

TEST_FETCH_RESPONSE = (
    "OK",
    [
        b"1 FETCH (BODY[] {1518}",
        bytearray(TEST_MESSAGE),
        b")",
        b"Fetch completed (0.0001 + 0.000 secs).",
    ],
)

BAD_FETCH_RESPONSE = ("BAD", [])
