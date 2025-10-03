"""Tests for the Tuya component."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya import DeviceListener
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_MOCKS = [
    "bzyd_45idzfufidgee7ir",  # https://github.com/orgs/home-assistant/discussions/717
    "bzyd_ssimhf6r8kgwepfb",  # https://github.com/orgs/home-assistant/discussions/718
    "cjkg_uenof8jd",  # https://github.com/home-assistant/core/issues/151825
    "ckmkzq_1yyqfw4djv9eii3q",  # https://github.com/home-assistant/core/issues/150856
    "cl_3r8gc33pnqsxfe1g",  # https://github.com/tuya/tuya-home-assistant/issues/754
    "cl_669wsr2w4cvinbh4",  # https://github.com/home-assistant/core/issues/150856
    "cl_cpbo62rn",  # https://github.com/orgs/home-assistant/discussions/539
    "cl_ebt12ypvexnixvtf",  # https://github.com/tuya/tuya-home-assistant/issues/754
    "cl_g1cp07dsqnbdbbki",  # https://github.com/home-assistant/core/issues/139966
    "cl_lfkr93x0ukp5gaia",  # https://github.com/home-assistant/core/issues/152826
    "cl_qqdxfdht",  # https://github.com/orgs/home-assistant/discussions/539
    "cl_rD7uqAAgQOpSA2Rx",  # https://github.com/home-assistant/core/issues/139966
    "cl_zah67ekd",  # https://github.com/home-assistant/core/issues/71242
    "clkg_nhyj64w2",  # https://github.com/home-assistant/core/issues/136055
    "clkg_wltqkykhni0papzj",  # https://github.com/home-assistant/core/issues/151635
    "clkg_xqvhthwkbmp3aghs",  # https://github.com/home-assistant/core/issues/139966
    "co2bj_yakol79dibtswovc",  # https://github.com/home-assistant/core/issues/151784
    "co2bj_yrr3eiyiacm31ski",  # https://github.com/orgs/home-assistant/discussions/842
    "cobj_hcdy5zrq3ikzthws",  # https://github.com/orgs/home-assistant/discussions/482
    "cs_b9oyi2yofflroq1g",  # https://github.com/home-assistant/core/issues/139966
    "cs_eguoms25tkxtf5u8",  # https://github.com/home-assistant/core/issues/152361
    "cs_ipmyy4nigpqcnd8q",  # https://github.com/home-assistant/core/pull/148726
    "cs_ka2wfrdoogpvgzfi",  # https://github.com/home-assistant/core/issues/119865
    "cs_qhxmvae667uap4zh",  # https://github.com/home-assistant/core/issues/141278
    "cs_vmxuxszzjwp5smli",  # https://github.com/home-assistant/core/issues/119865
    "cs_zibqa9dutqyaxym2",  # https://github.com/home-assistant/core/pull/125098
    "cwjwq_agwu93lr",  # https://github.com/orgs/home-assistant/discussions/79
    "cwwsq_lxfvx41gqdotrkgi",  # https://github.com/orgs/home-assistant/discussions/730
    "cwwsq_wfkzyy0evslzsmoi",  # https://github.com/home-assistant/core/issues/144745
    "cwysj_akln8rb04cav403q",  # https://github.com/home-assistant/core/pull/146599
    "cwysj_z3rpyvznfcch99aa",  # https://github.com/home-assistant/core/pull/146599
    "cz_0fHWRe8ULjtmnBNd",  # https://github.com/home-assistant/core/issues/139966
    "cz_0g1fmqh6d5io7lcn",  # https://github.com/home-assistant/core/issues/149704
    "cz_2iepauebcvo74ujc",  #  https://github.com/home-assistant/core/issues/141278
    "cz_2jxesipczks0kdct",  # https://github.com/home-assistant/core/issues/147149
    "cz_37mnhia3pojleqfh",  #  https://github.com/home-assistant/core/issues/146164
    "cz_39sy2g68gsjwo2xv",  #  https://github.com/home-assistant/core/issues/141278
    "cz_6fa7odsufen374x2",  #  https://github.com/home-assistant/core/issues/150029
    "cz_79a7z01v3n35kytb",  # https://github.com/orgs/home-assistant/discussions/221
    "cz_9ivirni8wemum6cw",  #  https://github.com/home-assistant/core/issues/139735
    "cz_AiHXxAyyn7eAkLQY",  # https://github.com/home-assistant/core/issues/150662
    "cz_CHLZe9HQ6QIXujVN",  # https://github.com/home-assistant/core/issues/149233
    "cz_HBRBzv1UVBVfF6SL",  # https://github.com/tuya/tuya-home-assistant/issues/754
    "cz_IGzCi97RpN2Lf9cu",  # https://github.com/home-assistant/core/issues/139966
    "cz_PGEkBctAbtzKOZng",  # https://github.com/home-assistant/core/issues/139966
    "cz_anwgf2xugjxpkfxb",  # https://github.com/orgs/home-assistant/discussions/539
    "cz_cuhokdii7ojyw8k2",  # https://github.com/home-assistant/core/issues/149704
    "cz_dhto3y4uachr1wll",  # https://github.com/orgs/home-assistant/discussions/169
    "cz_dntgh2ngvshfxpsz",  # https://github.com/home-assistant/core/issues/149704
    "cz_fencxse0bnut96ig",  # https://github.com/home-assistant/core/issues/63978
    "cz_gbtxrqfy9xcsakyp",  #  https://github.com/home-assistant/core/issues/141278
    "cz_gjnozsaz",  # https://github.com/orgs/home-assistant/discussions/482
    "cz_hA2GsgMfTQFTz9JL",  #  https://github.com/home-assistant/core/issues/148347
    "cz_hj0a5c7ckzzexu8l",  # https://github.com/home-assistant/core/issues/149704
    "cz_ik9sbig3mthx9hjz",  #  https://github.com/home-assistant/core/issues/141278
    "cz_ipabufmlmodje1ws",  # https://github.com/home-assistant/core/issues/63978
    "cz_iqhidxhhmgxk5eja",  # https://github.com/home-assistant/core/issues/149233
    "cz_jnbbxsb84gvvyfg5",  # https://github.com/tuya/tuya-home-assistant/issues/754
    "cz_mQUhiTg9kwydBFBd",  # https://github.com/home-assistant/core/issues/139966
    "cz_n8iVBAPLFKAAAszH",  #  https://github.com/home-assistant/core/issues/146164
    "cz_nkb0fmtlfyqosnvk",  # https://github.com/orgs/home-assistant/discussions/482
    "cz_nx8rv6jpe1tsnffk",  #  https://github.com/home-assistant/core/issues/148347
    "cz_piuensvr",  # https://github.com/home-assistant/core/issues/139966
    "cz_qm0iq4nqnrlzh4qc",  #  https://github.com/home-assistant/core/issues/141278
    "cz_qxJSyTLEtX5WrzA9",  # https://github.com/home-assistant/core/issues/139966
    "cz_raceucn29wk2yawe",  # https://github.com/tuya/tuya-home-assistant/issues/754
    "cz_sb6bwb1n8ma2c5q4",  #  https://github.com/home-assistant/core/issues/141278
    "cz_t0a4hwsf8anfsadp",  # https://github.com/home-assistant/core/issues/149704
    "cz_tf6qp8t3hl9h7m94",  #  https://github.com/home-assistant/core/issues/143209
    "cz_tkn2s79mzedk6pwr",  #  https://github.com/home-assistant/core/issues/146164
    "cz_vrbpx6h7fsi5mujb",  #  https://github.com/home-assistant/core/pull/149234
    "cz_vxqn72kwtosoy4d3",  #  https://github.com/home-assistant/core/issues/141278
    "cz_w0qqde0g",  # https://github.com/orgs/home-assistant/discussions/482
    "cz_wifvoilfrqeo6hvu",  #  https://github.com/home-assistant/core/issues/146164
    "cz_wrz6vzch8htux2zp",  #  https://github.com/home-assistant/core/issues/141278
    "cz_y4jnobxh",  # https://github.com/orgs/home-assistant/discussions/482
    "cz_yncyws7tu1q4cpsz",  # https://github.com/home-assistant/core/issues/150662
    "cz_z6pht25s3p0gs26q",  # https://github.com/home-assistant/core/issues/63978
    "dc_l3bpgg8ibsagon4x",  # https://github.com/home-assistant/core/issues/149704
    "dd_gaobbrxqiblcng2p",  # https://github.com/home-assistant/core/issues/149233
    "dj_0gyaslysqfp4gfis",  #  https://github.com/home-assistant/core/issues/149895
    "dj_8szt7whdvwpmxglk",  # https://github.com/home-assistant/core/issues/149704
    "dj_8ugheslg",  # https://github.com/home-assistant/core/issues/150856
    "dj_8y0aquaa8v6tho8w",  # https://github.com/home-assistant/core/issues/149704
    "dj_AqHUMdcbYzIq1Of4",  # https://github.com/orgs/home-assistant/discussions/539
    "dj_amx1bgdrfab6jngb",  # https://github.com/orgs/home-assistant/discussions/482
    "dj_bSXSSFArVKtc4DyC",  # https://github.com/orgs/home-assistant/discussions/539
    "dj_baf9tt9lb8t5uc7z",  # https://github.com/home-assistant/core/issues/149704
    "dj_c3nsqogqovapdpfj",  #  https://github.com/home-assistant/core/issues/146164
    "dj_d4g0fbsoaal841o6",  # https://github.com/home-assistant/core/issues/149704
    "dj_dbou1ap4",  # https://github.com/orgs/home-assistant/discussions/482
    "dj_djnozmdyqyriow8z",  # https://github.com/home-assistant/core/issues/149704
    "dj_ekwolitfjhxn55js",  # https://github.com/home-assistant/core/issues/149704
    "dj_fuupmcr2mb1odkja",  # https://github.com/home-assistant/core/issues/149704
    "dj_h4aX2JkHZNByQ4AV",  # https://github.com/home-assistant/core/issues/150662
    "dj_hp6orhaqm6as3jnv",  # https://github.com/home-assistant/core/issues/149704
    "dj_hpc8ddyfv85haxa7",  # https://github.com/home-assistant/core/issues/149704
    "dj_iayz2jmtlipjnxj7",  # https://github.com/home-assistant/core/issues/149704
    "dj_idnfq7xbx8qewyoa",  # https://github.com/home-assistant/core/issues/149704
    "dj_ilddqqih3tucdk68",  # https://github.com/home-assistant/core/issues/149704
    "dj_j1bgp31cffutizub",  # https://github.com/home-assistant/core/issues/149704
    "dj_kgaob37tz2muf3mi",  # https://github.com/home-assistant/core/issues/150856
    "dj_lmnt3uyltk1xffrt",  # https://github.com/home-assistant/core/issues/149704
    "dj_mki13ie507rlry4r",  # https://github.com/home-assistant/core/pull/126242
    "dj_nbumqpv8vz61enji",  # https://github.com/home-assistant/core/issues/149704
    "dj_nlxvjzy1hoeiqsg6",  # https://github.com/home-assistant/core/issues/149704
    "dj_oe0cpnjg",  # https://github.com/home-assistant/core/issues/149704
    "dj_qoqolwtqzfuhgghq",  # https://github.com/home-assistant/core/issues/149233
    "dj_riwp3k79",  # https://github.com/home-assistant/core/issues/149704
    "dj_tgewj70aowigv8fz",  # https://github.com/orgs/home-assistant/discussions/539
    "dj_tmsloaroqavbucgn",  # https://github.com/home-assistant/core/issues/149704
    "dj_ufq2xwuzd4nb0qdr",  # https://github.com/home-assistant/core/issues/149704
    "dj_vqwcnabamzrc2kab",  # https://github.com/home-assistant/core/issues/149704
    "dj_xdvitmhhmgefaeuq",  #  https://github.com/home-assistant/core/issues/146164
    "dj_xokdfs6kh5ednakk",  # https://github.com/home-assistant/core/issues/149704
    "dj_zakhnlpdiu0ycdxn",  # https://github.com/home-assistant/core/issues/149704
    "dj_zav1pa32pyxray78",  # https://github.com/home-assistant/core/issues/149704
    "dj_zputiamzanuk6yky",  # https://github.com/home-assistant/core/issues/149704
    "dlq_0tnvg2xaisqdadcf",  # https://github.com/home-assistant/core/issues/102769
    "dlq_cnpkf4xdmd9v49iq",  # https://github.com/home-assistant/core/pull/149320
    "dlq_dikb3dp6",  # https://github.com/home-assistant/core/pull/151601
    "dlq_jdj6ccklup7btq3a",  #  https://github.com/home-assistant/core/issues/143209
    "dlq_kxdr6su0c55p7bbo",  # https://github.com/home-assistant/core/issues/143499
    "dlq_r9kg2g1uhhyicycb",  #  https://github.com/home-assistant/core/issues/149650
    "dlq_z3jngbyubvwgfrcv",  # https://github.com/home-assistant/core/issues/150293
    "dr_pjvxl1wsyqxivsaf",  #  https://github.com/home-assistant/core/issues/84869
    "fs_g0ewlb1vmwqljzji",  # https://github.com/home-assistant/core/issues/141231
    "fs_ibytpo6fpnugft1c",  # https://github.com/home-assistant/core/issues/135541
    "fsd_9ecs16c53uqskxw6",  # https://github.com/home-assistant/core/issues/149233
    "gyd_lgekqfxdabipm3tn",  # https://github.com/home-assistant/core/issues/133173
    "hps_2aaelwxk",  # https://github.com/home-assistant/core/issues/149704
    "hps_wqashyqo",  #  https://github.com/home-assistant/core/issues/146180
    "hwsb_ircs2n82vgrozoew",  # https://github.com/home-assistant/core/issues/149233
    "jsq_r492ifwk6f2ssptb",  # https://github.com/home-assistant/core/issues/151488
    "jtmspro_xqeob8h6",  # https://github.com/orgs/home-assistant/discussions/517
    "kg_4nqs33emdwJxpQ8O",  # https://github.com/orgs/home-assistant/discussions/539
    "kg_5ftkaulg",  # https://github.com/orgs/home-assistant/discussions/539
    "kg_gbm9ata1zrzaez4a",  # https://github.com/home-assistant/core/issues/148347
    "kj_CAjWAxBUZt7QZHfz",  # https://github.com/home-assistant/core/issues/146023
    "kj_fsxtzzhujkrak2oy",  # https://github.com/orgs/home-assistant/discussions/439
    "kj_s4uzibibgzdxzowo",  #  https://github.com/home-assistant/core/issues/150246
    "kj_yrzylxax1qspdgpp",  # https://github.com/orgs/home-assistant/discussions/61
    "ks_j9fa8ahzac8uvlfl",  # https://github.com/orgs/home-assistant/discussions/329
    "kt_5wnlzekkstwcdsvm",  # https://github.com/home-assistant/core/pull/148646
    "kt_ibmmirhhq62mmf1g",  # https://github.com/home-assistant/core/pull/150077
    "kt_vdadlnmsorlhw4td",  # https://github.com/home-assistant/core/pull/149635
    "ldcg_9kbbfeho",  # https://github.com/orgs/home-assistant/discussions/482
    "mal_gyitctrjj1kefxp2",  # Alarm Host support
    "mc_oSQljE9YDqwCwTUA",  # https://github.com/home-assistant/core/issues/149233
    "mcs_6ywsnauy",  # https://github.com/orgs/home-assistant/discussions/482
    "mcs_7jIGJAymiH8OsFFb",  # https://github.com/home-assistant/core/issues/108301
    "mcs_8yhypbo7",  # https://github.com/orgs/home-assistant/discussions/482
    "mcs_hx5ztlztij4yxxvg",  #  https://github.com/home-assistant/core/issues/148347
    "mcs_oxslv1c9",  # https://github.com/home-assistant/core/issues/139966
    "mcs_qxu3flpqjsc1kqu3",  #  https://github.com/home-assistant/core/issues/141278
    "msp_3ddulzljdjjwkhoy",  # https://github.com/orgs/home-assistant/discussions/262
    "mzj_jlapoy5liocmtdvd",  # https://github.com/home-assistant/core/issues/150662
    "mzj_qavcakohisj5adyh",  # https://github.com/home-assistant/core/issues/141278
    "ntq_9mqdhwklpvnnvb7t",  # https://github.com/orgs/home-assistant/discussions/517
    "pc_t2afic7i3v1bwhfp",  # https://github.com/home-assistant/core/issues/149704
    "pc_trjopo1vdlt9q1tg",  # https://github.com/home-assistant/core/issues/149704
    "pc_tsbguim4trl6fa7g",  #  https://github.com/home-assistant/core/issues/146164
    "pc_yku9wsimasckdt15",  # https://github.com/orgs/home-assistant/discussions/482
    "pir_3amxzozho9xp4mkh",  # https://github.com/home-assistant/core/issues/149704
    "pir_fcdjzz3s",  # https://github.com/home-assistant/core/issues/149704
    "pir_j5jgnjvdaczeb6dc",  # https://github.com/orgs/home-assistant/discussions/582
    "pir_wqz93nrdomectyoz",  # https://github.com/home-assistant/core/issues/149704
    "qccdz_7bvgooyjhiua1yyq",  # https://github.com/home-assistant/core/issues/136207
    "qn_5ls2jw49hpczwqng",  # https://github.com/home-assistant/core/issues/149233
    "qt_TtXKwTMwiPpURWLJ",  # https://github.com/home-assistant/core/issues/139966
    "qxj_fsea1lat3vuktbt6",  # https://github.com/orgs/home-assistant/discussions/318
    "qxj_is2indt9nlth6esa",  # https://github.com/home-assistant/core/issues/136472
    "qxj_xbwbniyt6bgws9ia",  # https://github.com/orgs/home-assistant/discussions/823
    "rqbj_4iqe2hsfyd86kwwc",  # https://github.com/orgs/home-assistant/discussions/100
    "rs_d7woucobqi8ncacf",  # https://github.com/orgs/home-assistant/discussions/1021
    "sd_i6hyjg3af7doaswm",  # https://github.com/orgs/home-assistant/discussions/539
    "sd_lr33znaodtyarrrz",  # https://github.com/home-assistant/core/issues/141278
    "sfkzq_1fcnd8xk",  # https://github.com/orgs/home-assistant/discussions/539
    "sfkzq_d4vpmigg",  # https://github.com/home-assistant/core/issues/150662
    "sfkzq_ed7frwissyqrejic",  # https://github.com/home-assistant/core/pull/149236
    "sfkzq_nxquc5lb",  # https://github.com/home-assistant/core/issues/150662
    "sfkzq_o6dagifntoafakst",  # https://github.com/home-assistant/core/issues/148116
    "sfkzq_rzklytdei8i8vo37",  #  https://github.com/home-assistant/core/issues/146164
    "sgbj_DYgId0sz6zWlmmYu",  # https://github.com/orgs/home-assistant/discussions/583
    "sgbj_im2eqqhj72suwwko",  # https://github.com/home-assistant/core/issues/151082
    "sgbj_ulv4nnue7gqp0rjk",  # https://github.com/home-assistant/core/issues/149704
    "sj_rzeSU2h9uoklxEwq",  # https://github.com/home-assistant/core/issues/150683
    "sj_tgvtvdoc",  # https://github.com/orgs/home-assistant/discussions/482
    "sjz_ftbc8rp8ipksdfpv",  # https://github.com/orgs/home-assistant/discussions/51
    "sp_6bmk1remyscwyx6i",  # https://github.com/orgs/home-assistant/discussions/842
    "sp_drezasavompxpcgm",  # https://github.com/home-assistant/core/issues/149704
    "sp_nzauwyj3mcnjnf35",  #  https://github.com/home-assistant/core/issues/141278
    "sp_rjKXWRohlvOTyLBu",  # https://github.com/home-assistant/core/issues/149704
    "sp_rudejjigkywujjvs",  #  https://github.com/home-assistant/core/issues/146164
    "sp_sdd5f5f2dl5wydjf",  # https://github.com/home-assistant/core/issues/144087
    "swtz_3rzngbyy",  # https://github.com/orgs/home-assistant/discussions/688
    "szjcy_u5xgcpcngk3pfxb4",  # https://github.com/orgs/home-assistant/discussions/934
    "tdq_1aegphq4yfd50e6b",  # https://github.com/home-assistant/core/issues/143209
    "tdq_9htyiowaf5rtdhrv",  # https://github.com/home-assistant/core/issues/143209
    "tdq_cq1p0nt0a4rixnex",  # https://github.com/home-assistant/core/issues/146845
    "tdq_nockvv2k39vbrxxk",  # https://github.com/home-assistant/core/issues/145849
    "tdq_p6sqiuesvhmhvv4f",  # https://github.com/orgs/home-assistant/discussions/430
    "tdq_pu8uhxhwcp3tgoz7",  # https://github.com/home-assistant/core/issues/141278
    "tdq_uoa3mayicscacseb",  # https://github.com/home-assistant/core/issues/128911
    "tdq_x3o8epevyeo3z3oa",  # https://github.com/orgs/home-assistant/discussions/430
    "tyndj_pyakuuoc",  # https://github.com/home-assistant/core/issues/149704
    "wfcon_b25mh8sxawsgndck",  # https://github.com/home-assistant/core/issues/149704
    "wfcon_lieerjyy6l4ykjor",  #  https://github.com/home-assistant/core/issues/136055
    "wfcon_plp0gnfcacdeqk5o",  # https://github.com/home-assistant/core/issues/139966
    "wg2_2gowdgni",  # https://github.com/home-assistant/core/issues/150856
    "wg2_haclbl0qkqlf2qds",  # https://github.com/orgs/home-assistant/discussions/517
    "wg2_nwxr8qcu4seltoro",  # https://github.com/orgs/home-assistant/discussions/430
    "wg2_setmxeqgs63xwopm",  # https://github.com/orgs/home-assistant/discussions/539
    "wg2_tmwhss6ntjfc7prs",  # https://github.com/home-assistant/core/issues/150662
    "wg2_v7owd9tzcaninc36",  # https://github.com/orgs/home-assistant/discussions/539
    "wk_6kijc7nd",  # https://github.com/home-assistant/core/issues/136513
    "wk_IAYz2WK1th0cMLmL",  # https://github.com/orgs/home-assistant/discussions/842
    "wk_aqoouq7x",  # https://github.com/home-assistant/core/issues/146263
    "wk_ccpwojhalfxryigz",  # https://github.com/home-assistant/core/issues/145551
    "wk_cpmgn2cf",  # https://github.com/orgs/home-assistant/discussions/684
    "wk_fi6dne5tu4t1nm6j",  # https://github.com/orgs/home-assistant/discussions/243
    "wk_gc1bxoq2hafxpa35",  # https://github.com/home-assistant/core/issues/145551
    "wk_gogb05wrtredz3bs",  # https://github.com/home-assistant/core/issues/136337
    "wk_tfbhw0mg",  # https://github.com/home-assistant/core/issues/152282
    "wk_y5obtqhuztqsf2mj",  # https://github.com/home-assistant/core/issues/139735
    "wkcz_gc4b1mdw7kebtuyz",  #  https://github.com/home-assistant/core/issues/135617
    "wkf_9xfjixap",  # https://github.com/home-assistant/core/issues/139966
    "wkf_p3dbf6qs",  # https://github.com/home-assistant/core/issues/139966
    "wnykq_kzwdw5bpxlbs9h9g",  # https://github.com/orgs/home-assistant/discussions/842
    "wnykq_npbbca46yiug8ysk",  # https://github.com/orgs/home-assistant/discussions/539
    "wnykq_om518smspsaltzdi",  # https://github.com/home-assistant/core/issues/150662
    "wnykq_rqhxdyusjrwxyff6",  #  https://github.com/home-assistant/core/issues/133173
    "wsdcg_g2y6z3p3ja2qhyav",  # https://github.com/home-assistant/core/issues/102769
    "wsdcg_iq4ygaai",  # https://github.com/orgs/home-assistant/discussions/482
    "wsdcg_iv7hudlj",  #  https://github.com/home-assistant/core/issues/141278
    "wsdcg_krlcihrpzpc8olw9",  # https://github.com/orgs/home-assistant/discussions/517
    "wsdcg_lf36y5nwb8jkxwgg",  # https://github.com/orgs/home-assistant/discussions/539
    "wsdcg_qrztc3ev",  # https://github.com/home-assistant/core/issues/139966
    "wsdcg_vtA4pDd6PLUZzXgZ",  # https://github.com/orgs/home-assistant/discussions/482
    "wsdcg_xr3htd96",  # https://github.com/orgs/home-assistant/discussions/482
    "wsdcg_yqiqbaldtr0i7mru",  #  https://github.com/home-assistant/core/issues/136223
    "wxkg_ja5osu5g",  # https://github.com/orgs/home-assistant/discussions/482
    "wxkg_l8yaz4um5b3pwyvf",  # https://github.com/home-assistant/core/issues/93975
    "wxnbq_5l1ht8jygsyr1wn1",  # https://github.com/orgs/home-assistant/discussions/685
    "xdd_shx9mmadyyeaq88t",  # https://github.com/home-assistant/core/issues/151141
    "xnyjcn_pb0tc75khaik8qbg",  # https://github.com/home-assistant/core/pull/149237
    "ydkt_jevroj5aguwdbs2e",  # https://github.com/orgs/home-assistant/discussions/288
    "ygsb_l6ax0u6jwbz82atk",  #  https://github.com/home-assistant/core/issues/146319
    "ykq_bngwdjsr",  # https://github.com/orgs/home-assistant/discussions/482
    "ywbj_arywmw6h6vesoz5t",  #  https://github.com/home-assistant/core/issues/146164
    "ywbj_cjlutkuuvxnie17o",  #  https://github.com/home-assistant/core/issues/146164
    "ywbj_gf9dejhmzffgdyfj",  # https://github.com/home-assistant/core/issues/149704
    "ywbj_kscbebaf3s1eogvt",  #  https://github.com/home-assistant/core/issues/141278
    "ywbj_rccxox8p",  # https://github.com/orgs/home-assistant/discussions/625
    "ywcgq_h8lvyoahr6s6aybf",  # https://github.com/home-assistant/core/issues/145932
    "ywcgq_wtzwyhkev3b4ubns",  # https://github.com/home-assistant/core/issues/103818
    "zjq_nkkl7uzv",  # https://github.com/orgs/home-assistant/discussions/482
    "zndb_4ggkyflayu1h1ho9",  # https://github.com/home-assistant/core/pull/149317
    "zndb_v5jlnn5hwyffkhp3",  #  https://github.com/home-assistant/core/issues/143209
    "zndb_ze8faryrxr0glqnn",  # https://github.com/home-assistant/core/issues/138372
    "znnbq_0kllybtbzftaee7y",  # https://github.com/orgs/home-assistant/discussions/685
    "znnbq_6b3pbbuqbfabhfiq",  # https://github.com/orgs/home-assistant/discussions/707
    "znrb_db81ge24jctwx8lo",  #  https://github.com/home-assistant/core/issues/136513
    "zwjcy_gvygg3m8",  # https://github.com/orgs/home-assistant/discussions/949
    "zwjcy_myd45weu",  # https://github.com/orgs/home-assistant/discussions/482
]


class MockDeviceListener(DeviceListener):
    """Mocked DeviceListener for testing."""

    async def async_send_device_update(
        self,
        hass: HomeAssistant,
        device: CustomerDevice,
        updated_status_properties: dict[str, Any] | None = None,
    ) -> None:
        """Mock update device method."""
        property_list: list[str] = []
        if updated_status_properties:
            for key, value in updated_status_properties.items():
                if key not in device.status:
                    raise ValueError(
                        f"Property {key} not found in device status: {device.status}"
                    )
                device.status[key] = value
                property_list.append(key)
        self.update_device(device, property_list)
        await hass.async_block_till_done()


async def initialize_entry(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: CustomerDevice | list[CustomerDevice],
) -> None:
    """Initialize the Tuya component with a mock manager and config entry."""
    if not isinstance(mock_devices, list):
        mock_devices = [mock_devices]
    mock_manager.device_map = {device.id: device for device in mock_devices}

    # Setup
    mock_config_entry.add_to_hass(hass)

    # Initialize the component
    with patch(
        "homeassistant.components.tuya.CustomManager", return_value=mock_manager
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
