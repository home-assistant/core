"""Define common test values."""

TEST_DATA_HUB_TOPIC = "drop_connect/DROP-1_C0FFEE/255/stat"
TEST_DATA_HUB = '{"curFlow":5.77,"peakFlow":13.8,"usedToday":232.77,"avgUsed":76,"psi":62.2,"psiLow":61,"psiHigh":62,"water":"ON","bypass":"OFF","pMode":"HOME","battery":50,"notif":1,"leak":0}'

TEST_DATA_SALT_TOPIC = "drop_connect/DROP-1_C0FFEE/8/stat"
TEST_DATA_SALT = '{"salt":0}'

TEST_DATA_LEAK_TOPIC = "drop_connect/DROP-1_C0FFEE/20/stat"
TEST_DATA_LEAK = '{"battery":100,"leak":1,"temp":30.2}'

TEST_DATA_SOFTENER_TOPIC = "drop_connect/DROP-1_C0FFEE/0/stat"
TEST_DATA_SOFTENER = '{"curFlow":5.0,"bypass":"OFF","battery":20,"capacity":1000,"resInUse":1,"psi":999.9}'

TEST_DATA_FILTER_TOPIC = "drop_connect/DROP-1_C0FFEE/4/stat"
TEST_DATA_FILTER = '{"curFlow":19.84,"bypass":"OFF","battery":12,"psi":999.9}'

TEST_DATA_PROTECTION_VALVE_TOPIC = "drop_connect/DROP-1_C0FFEE/78/stat"
TEST_DATA_PROTECTION_VALVE = (
    '{"curFlow":7.1,"psi":61.3,"water":"ON","battery":0,"leak":1,"temp":21.2}'
)

TEST_DATA_PUMP_CONTROLLER_TOPIC = "drop_connect/DROP-1_C0FFEE/83/stat"
TEST_DATA_PUMP_CONTROLLER = '{"curFlow":2.2,"psi":62.2,"pump":1,"leak":1,"temp":24.5}'

TEST_DATA_RO_FILTER_TOPIC = "drop_connect/DROP-1_C0FFEE/95/stat"
TEST_DATA_RO_FILTER = (
    '{"leak":1,"tdsIn":164,"tdsOut":9,"cart1":59,"cart2":80,"cart3":59}'
)
