# Purpose:     Generate 'B0' message from received 'B1' data.

from optparse import OptionParser
from io import StringIO


# 1 publish
# dom_s20_8F35A5/cmnd/rfraw
# 177

# 2. subscribe
#


# Output: Example:
# AAB035051412DE05C802D5017223A0012332232323323232322332323232322323323223233223322323323232323223323232232323233455
# 0xAA: sync start 0xB0: command 0x35: len command (dec 53) 0x05: bucket count 0x14: repeats buckets 0-4 data 0x55:
# sync end


def getInputStr():
    # auxStr = '18:30:23 MQT: /sonoff/bridge/RESULT = {"RfRaw":{"Data":"AA B1 05 02FD 0E48 14CF 05E6 503C
    # 000000030102010103010103010101010101010104 55"}}'
    auxStr = StringIO.raw_input("Enter B1 line: ")
    iPos = auxStr.find('"}}')
    if iPos > 0:
        # Strip 'extra' info
        # auxStr = auxStr.lower()
        myfind = '"Data":"'
        iPos1 = auxStr.find(myfind)
        if iPos > 0:
            auxStr = auxStr[iPos1 + len(myfind) : iPos]
            print(auxStr)
        else:
            auxStr = ""
    return auxStr


def main(szInpStr, repVal):
    # print("%s" % szInpStr)
    if options.verbose:
        print("Repeat: %d" % repVal)
    listOfElem = szInpStr.split()
    # print(listOfElem)
    iNbrOfBuckets = int(listOfElem[2])
    # print("%d" % iNbrOfBuckets)
    # Start packing
    szOutAux = "AAB0xx"
    szOutAux += listOfElem[2]
    strHex = "%0.2X" % repVal
    # print(strHex)
    szOutAux += strHex
    for i in range(0, iNbrOfBuckets):
        strHex = listOfElem[i + 3]
        # iValue = int(strHex, 16)
        # print("Bucket %d: %s (%d)" % (i, strHex, iValue))
        szOutAux += strHex
    strHex = listOfElem[iNbrOfBuckets + 3]
    szOutAux += strHex
    szDataStr = strHex
    szOutAux += listOfElem[iNbrOfBuckets + 4]
    # print(szOutAux)
    iLength = len(szOutAux) / 2
    iLength -= 4
    # print(iLength)
    strHex = "%0.2X" % iLength
    print(strHex)
    szOutFinal = szOutAux.replace("xx", strHex)
    print(szOutFinal)

    iLength = len(szDataStr)
    strFirst = szDataStr[0]
    strLast = szDataStr[iLength - 1]
    strMiddle = szDataStr[1:-1]
    iLength = len(strMiddle)
    strMiddleNew = ""
    for i in range(0, iLength / 2):
        pos = i * 2
        strHex = strMiddle[pos : pos + 2]
        strMiddleNew += strHex
        strMiddleNew += " "
        # print(strHex)
    if options.debug:
        print("Sync: %s%s    Data: %s" % (strLast, strFirst, strMiddleNew))
    listOfElem1 = strMiddleNew.split()
    iNbrOfNibbles = len(listOfElem1)
    # print(listOfElem1)
    strFinalBits = "              "
    for i in range(0, iNbrOfNibbles):
        strHex = listOfElem1[i]
        if strHex == "12":
            strFinalBits += "0"
            strFinalBits += "  "
        elif strHex == "21":
            strFinalBits += "1"
            strFinalBits += "  "
    if options.debug:
        print("Sync %s" % strFinalBits)
    listOfElem2 = strFinalBits.split()
    iNbrOfBits = len(listOfElem2)
    # print(listOfElem2)
    strFinalDatas = ""
    for i in range(0, iNbrOfBits / 4):
        strHex = listOfElem2[i * 4]
        strHex += listOfElem2[i * 4 + 1]
        strHex += listOfElem2[i * 4 + 2]
        strHex += listOfElem2[i * 4 + 3]
        iValue = int(strHex, 2)
        strFinalDatas += str(iValue)
        # print("%s (%d-%s)" % (strHex, iValue, str(iValue)))

    if options.debug:
        print("Hex: %s" % strFinalDatas)

    sync_high = listOfElem[3 + 3]
    sync_low = listOfElem[3]
    bit_high_time = listOfElem[2 + 3]
    iValue2 = float(int(listOfElem[2 + 3], 16))
    iValue1 = float(int(listOfElem[1 + 3], 16))
    iValue = (iValue2 / (iValue2 + iValue1)) * 100
    bit_high_duty = hex(int(iValue))
    bit_low_time = listOfElem[1 + 3]
    iValue = (iValue1 / (iValue2 + iValue1)) * 100
    bit_low_duty = hex(int(iValue))

    syncBitCount = 0
    bit_count_sync_bit_count = hex(iNbrOfBits + syncBitCount)
    szOutAux = "7F "
    szOutAux += sync_high
    szOutAux += " "
    szOutAux += sync_low
    szOutAux += " "
    szOutAux += bit_high_time
    szOutAux += " "
    szOutAux += bit_high_duty
    szOutAux += " "
    szOutAux += bit_low_time
    szOutAux += " "
    szOutAux += bit_low_duty
    szOutAux += " "
    szOutAux += bit_count_sync_bit_count
    szOutAux += " "
    szOutAux += strFinalDatas

    szOutAux = szOutAux.replace("0x", "")
    szOutAux1 = szOutAux.replace(" ", "")
    iLength = len(szOutAux1) / 2
    strHex = "%0.2X" % iLength
    # print(strHex)
    if options.debug:
        print("\nThe data for command 0xA8 will be:")
        print("SYNC_HIGH: bucket 3: %s" % sync_high)
        print("SYNC_LOW: bucket 0: %s" % sync_low)
        print("BIT_HIGH_TIME: bucket 2: %s" % bit_high_time)
        print(
            "BIT_HIGH_DUTY: (100%% / (bucket 2 + bucket 1)) * bucket 2: %s (%d%%)"
            % (bit_high_duty, iValue)
        )
        print("BIT_LOW_TIME: bucket 1: %s" % bit_low_time)
        print(
            "BIT_LOW_DUTY: (100%% / (bucket 2 + bucket 1)) * bucket 1: %s (%d%%)"
            % (bit_low_duty, iValue)
        )
        print(
            "BIT_COUNT + SYNC_BIT_COUNT: %s (%d, SYNC_BIT_COUNT = %d)"
            % (bit_count_sync_bit_count, iNbrOfBits, syncBitCount)
        )
        print("Data: %s" % strFinalDatas)
        print(szOutAux1)
        print(
            "Protocol is 0x7F (unknown), Len xx is counting bytes: '%s' == 0x%s"
            % (szOutAux, strHex)
        )

    szOutFinal = "\n'AA A8 "
    szOutFinal += strHex
    szOutFinal += " "
    szOutFinal += szOutAux
    szOutFinal += " 55"
    szOutFinal += "'\n"
    print(szOutFinal)


usage = "usage: %prog [options]"
parser = OptionParser(usage=usage, version="%prog 0.2")
parser.add_option(
    "-e",
    "--dev",
    action="store",
    type="string",
    dest="device",
    help="device to send RfRaw B0 command",
)
parser.add_option(
    "-r",
    "--repeat",
    action="store",
    dest="repeat",
    default=20,
    help="number of times to repeat",
)
parser.add_option(
    "-d",
    "--debug",
    action="store_true",
    dest="debug",
    default=False,
    help="show debug info",
)
parser.add_option(
    "-v",
    "--verbose",
    action="store_true",
    dest="verbose",
    default=False,
    help="show more detailed info",
)
(options, args) = parser.parse_args()

# In program command line put two values (received Raw between '"' and desired repeats) Example: "AA B1 05 12DE 05C8
# 02D5 0172 23A0 0123322323233232323223323232323223233232232332233223233232323232233232322323232334 55" 20
if __name__ == "__main__":
    """
    print(len(args))
    if len(args) < 1:
        #parser.error("incorrect number of arguments. Use -h or --help")
        print(parser.print_help())
        exit(1)
    """
    while True:
        strInput = getInputStr()
        if len(strInput) > 0:
            main(strInput, options.repeat)
        else:
            break
    # print(parser.print_help())
