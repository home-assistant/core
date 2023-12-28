"""Define common test values."""

TEST_DATA_HUB_TOPIC = "drop_connect/DROP-1_C0FFEE/255"
TEST_DATA_HUB = (
    '{"curFlow":5.77,"peakFlow":13.8,"usedToday":232.77,"avgUsed":76,"psi":62.2,"psiLow":61,"psiHigh":62,'
    '"water":1,"bypass":0,"pMode":"home","battery":50,"notif":1,"leak":0}'
)
TEST_DATA_HUB_RESET = (
    '{"curFlow":0,"peakFlow":0,"usedToday":0,"avgUsed":0,"psi":0,"psiLow":0,"psiHigh":0,'
    '"water":0,"bypass":1,"pMode":"away","battery":0,"notif":0,"leak":0}'
)

TEST_DATA_SALT_TOPIC = "drop_connect/DROP-1_C0FFEE/8"
TEST_DATA_SALT = '{"salt":1}'
TEST_DATA_SALT_RESET = '{"salt":0}'

TEST_DATA_LEAK_TOPIC = "drop_connect/DROP-1_C0FFEE/20"
TEST_DATA_LEAK = '{"battery":100,"leak":1,"temp":68.2}'
TEST_DATA_LEAK_RESET = '{"battery":0,"leak":0,"temp":0}'

TEST_DATA_SOFTENER_TOPIC = "drop_connect/DROP-1_C0FFEE/0"
TEST_DATA_SOFTENER = (
    '{"curFlow":5.0,"bypass":0,"battery":20,"capacity":1000,"resInUse":1,"psi":50.5}'
)
TEST_DATA_SOFTENER_RESET = (
    '{"curFlow":0,"bypass":1,"battery":0,"capacity":0,"resInUse":0,"psi":null}'
)

TEST_DATA_FILTER_TOPIC = "drop_connect/DROP-1_C0FFEE/4"
TEST_DATA_FILTER = '{"curFlow":19.84,"bypass":0,"battery":12,"psi":38.2}'
TEST_DATA_FILTER_RESET = '{"curFlow":0,"bypass":1,"battery":0,"psi":null}'

TEST_DATA_PROTECTION_VALVE_TOPIC = "drop_connect/DROP-1_C0FFEE/78"
TEST_DATA_PROTECTION_VALVE = (
    '{"curFlow":7.1,"psi":61.3,"water":1,"battery":0,"leak":1,"temp":70.5}'
)
TEST_DATA_PROTECTION_VALVE_RESET = (
    '{"curFlow":0,"psi":0,"water":0,"battery":0,"leak":0,"temp":0}'
)

TEST_DATA_PUMP_CONTROLLER_TOPIC = "drop_connect/DROP-1_C0FFEE/83"
TEST_DATA_PUMP_CONTROLLER = '{"curFlow":2.2,"psi":62.2,"pump":1,"leak":1,"temp":68.8}'
TEST_DATA_PUMP_CONTROLLER_RESET = '{"curFlow":0,"psi":0,"pump":0,"leak":0,"temp":0}'

TEST_DATA_RO_FILTER_TOPIC = "drop_connect/DROP-1_C0FFEE/95"
TEST_DATA_RO_FILTER = (
    '{"leak":1,"tdsIn":164,"tdsOut":9,"cart1":59,"cart2":80,"cart3":59}'
)
TEST_DATA_RO_FILTER_RESET = (
    '{"leak":0,"tdsIn":0,"tdsOut":0,"cart1":0,"cart2":0,"cart3":0}'
)
