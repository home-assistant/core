"""Test constants."""

MOCK_LOCALE = "fr"

DATA_ERROR_WRONG_COUNTRY = {
    "errors": [
        {
            "message": "CatalogQuery/searchStore: Request failed with status code 400",
            "locations": [{"line": 18, "column": 9}],
            "correlationId": "e10ad58e-a4f9-4097-af5d-cafdbe0d8bbd",
            "serviceResponse": '{"errorCode":"errors.com.epicgames.catalog.invalid_country_code","errorMessage":"Sorry the value you entered: en-US, does not appear to be a valid ISO country code.","messageVars":["en-US"],"numericErrorCode":5222,"originatingService":"com.epicgames.catalog.public","intent":"prod","errorStatus":400}',
            "stack": None,
            "path": ["Catalog", "searchStore"],
        }
    ],
    "data": {"Catalog": {"searchStore": None}},
    "extensions": {},
}

# free games
DATA_FREE_GAMES = {
    "data": {
        "Catalog": {
            "searchStore": {
                "elements": [
                    {
                        "title": "Rising Storm 2: Vietnam",
                        "id": "b19d810d322240e7b37bcf84ffac60ce",
                        "namespace": "3542a1df211e492bb2abecb7c734f7f9",
                        "description": "Red Orchestra Series' take on Vietnam: 64-player MP matches; 20+ maps; US Army & Marines, PAVN/NVA, NLF/VC; Australians and ARVN forces; 50+ weapons; 4 flyable helicopters; mines, traps and tunnels; Brutal. Authentic. Gritty. Character customization.",
                        "effectiveDate": "2020-10-08T15:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/3542a1df211e492bb2abecb7c734f7f9/offer/EGS_RisingStorm2Vietnam_AntimatterGamesTripwireInteractive_S3-2560x1440-e08edd93cb71bf15b50a74f3de2d17b0.jpg",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/3542a1df211e492bb2abecb7c734f7f9/offer/EGS_RisingStorm2Vietnam_AntimatterGamesTripwireInteractive_S4-1200x1600-5e3b2f8107e17cc008237e52761d67e5.jpg",
                            },
                            {
                                "type": "DieselStoreFrontWide",
                                "url": "https://cdn1.epicgames.com/3542a1df211e492bb2abecb7c734f7f9/offer/EGS_RisingStorm2Vietnam_AntimatterGamesTripwireInteractive_S3-2560x1440-e08edd93cb71bf15b50a74f3de2d17b0.jpg",
                            },
                            {
                                "type": "DieselStoreFrontTall",
                                "url": "https://cdn1.epicgames.com/3542a1df211e492bb2abecb7c734f7f9/offer/EGS_RisingStorm2Vietnam_AntimatterGamesTripwireInteractive_S4-1200x1600-5e3b2f8107e17cc008237e52761d67e5.jpg",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/3542a1df211e492bb2abecb7c734f7f9/offer/EGS_RisingStorm2Vietnam_AntimatterGamesTripwireInteractive_S4-1200x1600-5e3b2f8107e17cc008237e52761d67e5.jpg",
                            },
                            {
                                "type": "CodeRedemption_340x440",
                                "url": "https://cdn1.epicgames.com/3542a1df211e492bb2abecb7c734f7f9/offer/EGS_RisingStorm2Vietnam_AntimatterGamesTripwireInteractive_S4-1200x1600-5e3b2f8107e17cc008237e52761d67e5.jpg",
                            },
                        ],
                        "seller": {
                            "id": "o-2baznhy8tfh7fmyb55ul656v7ggt7r",
                            "name": "Tripwire Interactive",
                        },
                        "productSlug": "rising-storm-2-vietnam/home",
                        "urlSlug": "risingstorm2vietnam",
                        "url": None,
                        "items": [
                            {
                                "id": "685765c3f37049c49b45bea4173725d2",
                                "namespace": "3542a1df211e492bb2abecb7c734f7f9",
                            },
                            {
                                "id": "c7c6d65ac4cc4ef0ae12e8e89f134684",
                                "namespace": "3542a1df211e492bb2abecb7c734f7f9",
                            },
                        ],
                        "customAttributes": [
                            {"key": "com.epicgames.app.blacklist", "value": "[]"},
                            {"key": "publisherName", "value": "Tripwire Interactive"},
                            {"key": "developerName", "value": "Antimatter Games"},
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "rising-storm-2-vietnam/home",
                            },
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "games/edition"},
                            {"path": "games/edition/base"},
                            {"path": "applications"},
                        ],
                        "tags": [
                            {"id": "1216"},
                            {"id": "21122"},
                            {"id": "21125"},
                            {"id": "21129"},
                            {"id": "14346"},
                            {"id": "9547"},
                            {"id": "16011"},
                            {"id": "15375"},
                            {"id": "21135"},
                            {"id": "21138"},
                            {"id": "1299"},
                            {"id": "16979"},
                            {"id": "21139"},
                            {"id": "21140"},
                            {"id": "17493"},
                            {"id": "21141"},
                            {"id": "22485"},
                            {"id": "18777"},
                            {"id": "18778"},
                            {"id": "1115"},
                            {"id": "21148"},
                            {"id": "21149"},
                            {"id": "14944"},
                            {"id": "19242"},
                            {"id": "18607"},
                            {"id": "1203"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "rising-storm-2-vietnam",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 2199,
                                "originalPrice": 2199,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€21.99",
                                    "discountPrice": "€21.99",
                                    "intermediatePrice": "€21.99",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": {
                            "promotionalOffers": [],
                            "upcomingPromotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2022-11-03T15:00:00.000Z",
                                            "endDate": "2022-11-10T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 0,
                                            },
                                        }
                                    ]
                                }
                            ],
                        },
                    },
                    {
                        "title": "Idle Champions of the Forgotten Realms",
                        "id": "a9748abde1c94b66aae5250bb9fc5503",
                        "namespace": "7e508f543b05465abe3a935960eb70ac",
                        "description": "Idle Champions is a licensed Dungeons & Dragons strategy management video game uniting iconic characters from novels, campaigns, and shows into one epic adventure.",
                        "effectiveDate": "2021-02-16T17:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/offer/7e508f543b05465abe3a935960eb70ac/EGS_IdleChampionsoftheForgottenRealms_CodenameEntertainment_S2_1200x1600-dd9a8f25ad56089231f43cf639bde217",
                            },
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/offer/7e508f543b05465abe3a935960eb70ac/EGS_IdleChampionsoftheForgottenRealms_CodenameEntertainment_S1_2560x1440-e2a1ffd224f443594d5deff3a47a45e2",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/offer/7e508f543b05465abe3a935960eb70ac/EGS_IdleChampionsoftheForgottenRealms_CodenameEntertainment_S2_1200x1600-dd9a8f25ad56089231f43cf639bde217",
                            },
                            {
                                "type": "DieselStoreFrontTall",
                                "url": "https://cdn1.epicgames.com/offer/7e508f543b05465abe3a935960eb70ac/EGS_IdleChampionsoftheForgottenRealms_CodenameEntertainment_S2_1200x1600-dd9a8f25ad56089231f43cf639bde217",
                            },
                            {
                                "type": "DieselStoreFrontWide",
                                "url": "https://cdn1.epicgames.com/offer/7e508f543b05465abe3a935960eb70ac/EGS_IdleChampionsoftheForgottenRealms_CodenameEntertainment_S1_2560x1440-e2a1ffd224f443594d5deff3a47a45e2",
                            },
                        ],
                        "seller": {
                            "id": "o-3kpjwtwqwfl2p9wdwvpad7yqz4kt6c",
                            "name": "Codename Entertainment",
                        },
                        "productSlug": "idle-champions-of-the-forgotten-realms",
                        "urlSlug": "banegeneralaudience",
                        "url": None,
                        "items": [
                            {
                                "id": "9a4e1a1eb6b140f6a9e5e4dcb5a2bf55",
                                "namespace": "7e508f543b05465abe3a935960eb70ac",
                            }
                        ],
                        "customAttributes": [
                            {"key": "com.epicgames.app.blacklist", "value": "KR"},
                            {"key": "publisherName", "value": "Codename Entertainment"},
                            {"key": "developerName", "value": "Codename Entertainment"},
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "idle-champions-of-the-forgotten-realms",
                            },
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "games/edition"},
                            {"path": "games/edition/base"},
                            {"path": "applications"},
                        ],
                        "tags": [
                            {"id": "21136"},
                            {"id": "21122"},
                            {"id": "21138"},
                            {"id": "21139"},
                            {"id": "1188"},
                            {"id": "1141"},
                            {"id": "1370"},
                            {"id": "1115"},
                            {"id": "9547"},
                            {"id": "21149"},
                            {"id": "21119"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "idle-champions-of-the-forgotten-realms",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 0,
                                "originalPrice": 0,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "0",
                                    "discountPrice": "0",
                                    "intermediatePrice": "0",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": {
                            "promotionalOffers": [],
                            "upcomingPromotionalOffers": [],
                        },
                    },
                    {
                        "title": "Hundred Days - Winemaking Simulator",
                        "id": "141eee80fbe041d48e16e7b998829295",
                        "namespace": "4d8b727a49144090b103f6b6ba471e71",
                        "description": "Winemaking could be your best adventure. Make the best wine interacting with soil and nature and take your winery to the top. Your beautiful journey into the winemaking tradition starts now.",
                        "effectiveDate": "2021-05-13T14:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/4d8b727a49144090b103f6b6ba471e71/offer/EGS_HundredDaysWinemakingSimulatorDEMO_BrokenArmsGames_Demo_G1C_00-1920x1080-0ffeb0645f0badb615627b481b4a913e.jpg",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/4d8b727a49144090b103f6b6ba471e71/offer/EGS_HundredDaysWinemakingSimulatorDEMO_BrokenArmsGames_Demo_S2-1200x1600-35531ec1fa868e3876fac76471a24017.jpg",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/4d8b727a49144090b103f6b6ba471e71/offer/EGS_HundredDaysWinemakingSimulatorDEMO_BrokenArmsGames_Demo_S2-1200x1600-35531ec1fa868e3876fac76471a24017.jpg",
                            },
                            {
                                "type": "CodeRedemption_340x440",
                                "url": "https://cdn1.epicgames.com/4d8b727a49144090b103f6b6ba471e71/offer/EGS_HundredDaysWinemakingSimulatorDEMO_BrokenArmsGames_Demo_S2-1200x1600-35531ec1fa868e3876fac76471a24017.jpg",
                            },
                            {
                                "type": "DieselStoreFrontWide",
                                "url": "https://cdn1.epicgames.com/4d8b727a49144090b103f6b6ba471e71/offer/EGS_HundredDaysWinemakingSimulatorDEMO_BrokenArmsGames_Demo_S1-2560x1440-8f0dd95b6027cd1243361d430b3bf552.jpg",
                            },
                            {
                                "type": "DieselStoreFrontTall",
                                "url": "https://cdn1.epicgames.com/4d8b727a49144090b103f6b6ba471e71/offer/EGS_HundredDaysWinemakingSimulatorDEMO_BrokenArmsGames_Demo_S2-1200x1600-35531ec1fa868e3876fac76471a24017.jpg",
                            },
                        ],
                        "seller": {
                            "id": "o-ty5rvlnsbgdnfffytsywat86gcedkm",
                            "name": "Broken Arms Games srls",
                        },
                        "productSlug": "hundred-days-winemaking-simulator",
                        "urlSlug": "hundred-days-winemaking-simulator",
                        "url": None,
                        "items": [
                            {
                                "id": "03cacb8754f243bfbc536c9dda0eb32e",
                                "namespace": "4d8b727a49144090b103f6b6ba471e71",
                            }
                        ],
                        "customAttributes": [
                            {"key": "com.epicgames.app.blacklist", "value": "[]"},
                            {"key": "developerName", "value": "Broken Arms Games"},
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "hundred-days-winemaking-simulator",
                            },
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "games/edition"},
                            {"path": "games/edition/base"},
                            {"path": "applications"},
                        ],
                        "tags": [
                            {"id": "1188"},
                            {"id": "21894"},
                            {"id": "21127"},
                            {"id": "19242"},
                            {"id": "21130"},
                            {"id": "16011"},
                            {"id": "9547"},
                            {"id": "1263"},
                            {"id": "15375"},
                            {"id": "18607"},
                            {"id": "1393"},
                            {"id": "21138"},
                            {"id": "16979"},
                            {"id": "21140"},
                            {"id": "17493"},
                            {"id": "21141"},
                            {"id": "18777"},
                            {"id": "1370"},
                            {"id": "18778"},
                            {"id": "21146"},
                            {"id": "1115"},
                            {"id": "21149"},
                            {"id": "10719"},
                            {"id": "21119"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "hundred-days-winemaking-simulator",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 1999,
                                "originalPrice": 1999,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€19.99",
                                    "discountPrice": "€19.99",
                                    "intermediatePrice": "€19.99",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": None,
                    },
                    {
                        "title": "Shadow of the Tomb Raider: Definitive Edition",
                        "id": "ee7f3c6725fd4fd4b8aeab8622cb770e",
                        "namespace": "4b5461ca8d1c488787b5200b420de066",
                        "description": "In Shadow of the Tomb Raider Definitive Edition experience the final chapter of Lara’s origin as she is forged into the Tomb Raider she is destined to be.",
                        "effectiveDate": "2021-12-30T16:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "CodeRedemption_340x440",
                                "url": "https://cdn1.epicgames.com/offer/4b5461ca8d1c488787b5200b420de066/egs-shadowofthetombraiderdefinitiveedition-eidosmontralcrystaldynamicsnixxessoftware-s4-1200x1600-7ee40d6fa744_1200x1600-950cdb624cc75d04fe3c8c0b62ce98de",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/offer/4b5461ca8d1c488787b5200b420de066/egs-shadowofthetombraiderdefinitiveedition-eidosmontralcrystaldynamicsnixxessoftware-s4-1200x1600-7ee40d6fa744_1200x1600-950cdb624cc75d04fe3c8c0b62ce98de",
                            },
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/offer/4b5461ca8d1c488787b5200b420de066/egs-shadowofthetombraiderdefinitiveedition-eidosmontralcrystaldynamicsnixxessoftware-s1-2560x1440-eca6506e95a1_2560x1440-193582a5fd76a593804e0171d6395cf4",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/offer/4b5461ca8d1c488787b5200b420de066/egs-shadowofthetombraiderdefinitiveedition-eidosmontralcrystaldynamicsnixxessoftware-s4-1200x1600-7ee40d6fa744_1200x1600-950cdb624cc75d04fe3c8c0b62ce98de",
                            },
                            {
                                "type": "DieselStoreFrontTall",
                                "url": "https://cdn1.epicgames.com/offer/4b5461ca8d1c488787b5200b420de066/egs-shadowofthetombraiderdefinitiveedition-eidosmontralcrystaldynamicsnixxessoftware-s4-1200x1600-7ee40d6fa744_1200x1600-950cdb624cc75d04fe3c8c0b62ce98de",
                            },
                            {
                                "type": "DieselStoreFrontWide",
                                "url": "https://cdn1.epicgames.com/offer/4b5461ca8d1c488787b5200b420de066/egs-shadowofthetombraiderdefinitiveedition-eidosmontralcrystaldynamicsnixxessoftware-s1-2560x1440-eca6506e95a1_2560x1440-193582a5fd76a593804e0171d6395cf4",
                            },
                        ],
                        "seller": {
                            "id": "o-7petn7mrlk8g86ktqm7uglcr7lfaja",
                            "name": "Square Enix",
                        },
                        "productSlug": "shadow-of-the-tomb-raider",
                        "urlSlug": "shadow-of-the-tomb-raider",
                        "url": None,
                        "items": [
                            {
                                "id": "e7f90759e0544e42be9391d10a5c6000",
                                "namespace": "4b5461ca8d1c488787b5200b420de066",
                            }
                        ],
                        "customAttributes": [
                            {"key": "com.epicgames.app.blacklist", "value": "[]"},
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "shadow-of-the-tomb-raider",
                            },
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "games/edition"},
                            {"path": "games/edition/base"},
                            {"path": "applications"},
                        ],
                        "tags": [
                            {"id": "1216"},
                            {"id": "21122"},
                            {"id": "18051"},
                            {"id": "1188"},
                            {"id": "21894"},
                            {"id": "21127"},
                            {"id": "9547"},
                            {"id": "9549"},
                            {"id": "21138"},
                            {"id": "21139"},
                            {"id": "21140"},
                            {"id": "21109"},
                            {"id": "21141"},
                            {"id": "22485"},
                            {"id": "1370"},
                            {"id": "21146"},
                            {"id": "1117"},
                            {"id": "21149"},
                            {"id": "21119"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "shadow-of-the-tomb-raider",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 1319,
                                "originalPrice": 3999,
                                "voucherDiscount": 0,
                                "discount": 2680,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€39.99",
                                    "discountPrice": "€13.19",
                                    "intermediatePrice": "€13.19",
                                },
                            },
                            "lineOffers": [
                                {
                                    "appliedRules": [
                                        {
                                            "id": "35111a3c715340d08910a9f6a5b3e846",
                                            "endDate": "2022-11-01T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE"
                                            },
                                        }
                                    ]
                                }
                            ],
                        },
                        "promotions": {
                            "promotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2022-10-18T15:00:00.000Z",
                                            "endDate": "2022-11-01T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 33,
                                            },
                                        }
                                    ]
                                }
                            ],
                            "upcomingPromotionalOffers": [],
                        },
                    },
                    {
                        "title": "Terraforming Mars",
                        "id": "f2496286331e405793d69807755b7b23",
                        "namespace": "25d726130e6c4fe68f88e71933bda955",
                        "description": "The taming of the Red Planet has begun!\n\nControl your corporation, play project cards, build up production, place your cities and green areas on the map, and race for milestones and awards!\n\nWill your corporation lead the way into humanity's new era?",
                        "effectiveDate": "2022-05-05T15:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/spt-assets/5199b206e46947ebad5e5c282e95776f/terraforming-mars-offer-1j70f.jpg",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/spt-assets/5199b206e46947ebad5e5c282e95776f/download-terraforming-mars-offer-13t2e.jpg",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/spt-assets/5199b206e46947ebad5e5c282e95776f/download-terraforming-mars-offer-13t2e.jpg",
                            },
                        ],
                        "seller": {
                            "id": "o-4x4bpaww55p5g3f6xpyqe2cneqxd5d",
                            "name": "Asmodee",
                        },
                        "productSlug": None,
                        "urlSlug": "24cdfcde68bf4a7e8b8618ac2c0c460b",
                        "url": None,
                        "items": [
                            {
                                "id": "ee49486d7346465dba1f1dec85725aee",
                                "namespace": "25d726130e6c4fe68f88e71933bda955",
                            }
                        ],
                        "customAttributes": [
                            {"key": "autoGeneratedPrice", "value": "false"},
                            {"key": "isManuallySetPCReleaseDate", "value": "true"},
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games/edition/base"},
                            {"path": "games/edition"},
                            {"path": "games"},
                        ],
                        "tags": [
                            {"id": "18051"},
                            {"id": "1188"},
                            {"id": "21125"},
                            {"id": "1386"},
                            {"id": "9547"},
                            {"id": "21138"},
                            {"id": "1203"},
                            {"id": "1299"},
                            {"id": "21139"},
                            {"id": "21140"},
                            {"id": "21141"},
                            {"id": "1370"},
                            {"id": "1115"},
                            {"id": "21148"},
                            {"id": "21149"},
                            {"id": "10719"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "terraforming-mars-18c3ad",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [
                            {
                                "pageSlug": "terraforming-mars-18c3ad",
                                "pageType": "productHome",
                            }
                        ],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 1399,
                                "originalPrice": 1999,
                                "voucherDiscount": 0,
                                "discount": 600,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€19.99",
                                    "discountPrice": "€13.99",
                                    "intermediatePrice": "€13.99",
                                },
                            },
                            "lineOffers": [
                                {
                                    "appliedRules": [
                                        {
                                            "id": "8e9732952e714f6583416e66fc451cd7",
                                            "endDate": "2022-11-01T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE"
                                            },
                                        }
                                    ]
                                }
                            ],
                        },
                        "promotions": {
                            "promotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2022-10-18T15:00:00.000Z",
                                            "endDate": "2022-11-01T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 70,
                                            },
                                        }
                                    ]
                                }
                            ],
                            "upcomingPromotionalOffers": [],
                        },
                    },
                    {
                        "title": "Car Mechanic Simulator 2018",
                        "id": "5eb27cf1747c40b5a0d4f5492774678d",
                        "namespace": "226306adde104c9092247dcd4bfa1499",
                        "description": "Build and expand your repair service empire in this incredibly detailed and highly realistic simulation game, where attention to car detail is astonishing. Find classic, unique cars in the new Barn Find module and Junkyard module.",
                        "effectiveDate": "2022-06-23T15:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/offer/226306adde104c9092247dcd4bfa1499/EGS_CarMechanicSimulator2018_RedDotGames_S2_1200x1600-f285924f9144353f57ac4631f0c689e6",
                            },
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/offer/226306adde104c9092247dcd4bfa1499/EGS_CarMechanicSimulator2018_RedDotGames_S1_2560x1440-3489ef1499e64c168fdf4b14926d2c23",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/offer/226306adde104c9092247dcd4bfa1499/EGS_CarMechanicSimulator2018_RedDotGames_S2_1200x1600-f285924f9144353f57ac4631f0c689e6",
                            },
                        ],
                        "seller": {
                            "id": "o-5n5cbrasl5yzexjc529rypg8eh8lfb",
                            "name": "PlayWay",
                        },
                        "productSlug": "car-mechanic-simulator-2018",
                        "urlSlug": "car-mechanic-simulator-2018",
                        "url": None,
                        "items": [
                            {
                                "id": "49a3a8597c4240ecaf1f9068106c9869",
                                "namespace": "226306adde104c9092247dcd4bfa1499",
                            }
                        ],
                        "customAttributes": [
                            {"key": "com.epicgames.app.blacklist", "value": "[]"},
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "car-mechanic-simulator-2018",
                            },
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "games/edition"},
                            {"path": "games/edition/base"},
                            {"path": "applications"},
                        ],
                        "tags": [
                            {"id": "21120"},
                            {"id": "1188"},
                            {"id": "21127"},
                            {"id": "9547"},
                            {"id": "1393"},
                            {"id": "21138"},
                            {"id": "21139"},
                            {"id": "21140"},
                            {"id": "21141"},
                            {"id": "1370"},
                            {"id": "21146"},
                            {"id": "21148"},
                            {"id": "21149"},
                            {"id": "21119"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "car-mechanic-simulator-2018",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 1599,
                                "originalPrice": 1599,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€15.99",
                                    "discountPrice": "€15.99",
                                    "intermediatePrice": "€15.99",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": None,
                    },
                    {
                        "title": "A Game Of Thrones: The Board Game Digital Edition",
                        "id": "a125d72a47a1490aba78c4e79a40395d",
                        "namespace": "1b737464d3c441f8956315433be02d3b",
                        "description": "It is the digital adaptation of the top-selling strategy board game from Fantasy Flight Games.",
                        "effectiveDate": "2022-06-23T15:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/spt-assets/61c1413e3db0423f9ddd4a5edbee717e/a-game-of-thrones-offer-11gxu.jpg",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/spt-assets/61c1413e3db0423f9ddd4a5edbee717e/download-a-game-of-thrones-offer-1q8ei.jpg",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/spt-assets/61c1413e3db0423f9ddd4a5edbee717e/download-a-game-of-thrones-offer-1q8ei.jpg",
                            },
                        ],
                        "seller": {
                            "id": "o-4x4bpaww55p5g3f6xpyqe2cneqxd5d",
                            "name": "Asmodee",
                        },
                        "productSlug": None,
                        "urlSlug": "ce6f7ab4edab4cc2aa7e0ff4c19540e2",
                        "url": None,
                        "items": [
                            {
                                "id": "dc6ae31efba7401fa72ed93f0bd37c6a",
                                "namespace": "1b737464d3c441f8956315433be02d3b",
                            }
                        ],
                        "customAttributes": [
                            {"key": "autoGeneratedPrice", "value": "false"},
                            {"key": "isManuallySetPCReleaseDate", "value": "true"},
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games/edition/base"},
                            {"path": "games/edition"},
                            {"path": "games"},
                        ],
                        "tags": [
                            {"id": "18051"},
                            {"id": "1188"},
                            {"id": "21125"},
                            {"id": "9547"},
                            {"id": "21138"},
                            {"id": "1203"},
                            {"id": "1299"},
                            {"id": "21139"},
                            {"id": "21140"},
                            {"id": "21141"},
                            {"id": "1370"},
                            {"id": "1115"},
                            {"id": "21149"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "a-game-of-thrones-5858a3",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [
                            {
                                "pageSlug": "a-game-of-thrones-5858a3",
                                "pageType": "productHome",
                            }
                        ],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 1399,
                                "originalPrice": 1999,
                                "voucherDiscount": 0,
                                "discount": 600,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€19.99",
                                    "discountPrice": "€13.99",
                                    "intermediatePrice": "€13.99",
                                },
                            },
                            "lineOffers": [
                                {
                                    "appliedRules": [
                                        {
                                            "id": "689de276cf3245a7bffdfa0d20500150",
                                            "endDate": "2022-11-01T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE"
                                            },
                                        }
                                    ]
                                }
                            ],
                        },
                        "promotions": {
                            "promotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2022-10-18T15:00:00.000Z",
                                            "endDate": "2022-11-01T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 70,
                                            },
                                        }
                                    ]
                                }
                            ],
                            "upcomingPromotionalOffers": [],
                        },
                    },
                    {
                        "title": "Filament",
                        "id": "296453e71c884f95aecf4d582cf66915",
                        "namespace": "89fb09a222a54e53b692e9c36e68d0a1",
                        "description": "Solve challenging cable-based puzzles and uncover what really happened to the crew of The Alabaster. Now with Hint System (for those ultra tricky puzzles).",
                        "effectiveDate": "2022-08-11T11:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/spt-assets/5a72e62648d747189d2f5e7abb47444c/filament-offer-qrwye.jpg",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/spt-assets/5a72e62648d747189d2f5e7abb47444c/download-filament-offer-mk58q.jpg",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/spt-assets/5a72e62648d747189d2f5e7abb47444c/download-filament-offer-mk58q.jpg",
                            },
                        ],
                        "seller": {
                            "id": "o-fnqgc5v2xczx9fgawvcejwj88z2mnx",
                            "name": "Kasedo Games Ltd",
                        },
                        "productSlug": None,
                        "urlSlug": "323de464947e4ee5a035c525b6b78021",
                        "url": None,
                        "items": [
                            {
                                "id": "d4fa1325ef014725a89cc40e9b99e43d",
                                "namespace": "89fb09a222a54e53b692e9c36e68d0a1",
                            }
                        ],
                        "customAttributes": [
                            {"key": "autoGeneratedPrice", "value": "false"},
                            {"key": "isManuallySetPCReleaseDate", "value": "true"},
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games/edition/base"},
                            {"path": "games/edition"},
                            {"path": "games"},
                        ],
                        "tags": [
                            {"id": "1298"},
                            {"id": "21894"},
                            {"id": "19847"},
                            {"id": "1370"},
                            {"id": "9547"},
                            {"id": "9549"},
                            {"id": "1263"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "filament-332a92",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [
                            {"pageSlug": "filament-332a92", "pageType": "productHome"}
                        ],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 1699,
                                "originalPrice": 1699,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€16.99",
                                    "discountPrice": "€16.99",
                                    "intermediatePrice": "€16.99",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": {
                            "promotionalOffers": [],
                            "upcomingPromotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2022-11-03T15:00:00.000Z",
                                            "endDate": "2022-11-10T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 0,
                                            },
                                        }
                                    ]
                                }
                            ],
                        },
                    },
                    {
                        "title": "Warhammer 40,000: Mechanicus - Standard Edition",
                        "id": "559b16fa81134dce83b5b8b7cf67b5b3",
                        "namespace": "144f9e231e2846d1a4381d9bb678f69d",
                        "description": "Take control of the most technologically advanced army in the Imperium - The Adeptus Mechanicus. Your every decision will weigh heavily on the outcome of the mission, in this turn-based tactical game. Will you be blessed by the Omnissiah?",
                        "effectiveDate": "2022-08-11T11:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/spt-assets/d26f2f9ea65c462dbd39040ae8389d36/warhammer-mechanicus-offer-17fnz.jpg",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/spt-assets/d26f2f9ea65c462dbd39040ae8389d36/download-warhammer-mechanicus-offer-1f6bv.jpg",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/spt-assets/d26f2f9ea65c462dbd39040ae8389d36/download-warhammer-mechanicus-offer-1f6bv.jpg",
                            },
                        ],
                        "seller": {
                            "id": "o-fnqgc5v2xczx9fgawvcejwj88z2mnx",
                            "name": "Kasedo Games Ltd",
                        },
                        "productSlug": None,
                        "urlSlug": "f37159d9bd96489ab1b99bdad1ee796c",
                        "url": None,
                        "items": [
                            {
                                "id": "f923ad9f3428472ab67baa4618c205a0",
                                "namespace": "144f9e231e2846d1a4381d9bb678f69d",
                            }
                        ],
                        "customAttributes": [
                            {"key": "autoGeneratedPrice", "value": "false"},
                            {"key": "isManuallySetPCReleaseDate", "value": "true"},
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games/edition/base"},
                            {"path": "games/edition"},
                            {"path": "games"},
                        ],
                        "tags": [
                            {"id": "21894"},
                            {"id": "19847"},
                            {"id": "1386"},
                            {"id": "1115"},
                            {"id": "9547"},
                            {"id": "9549"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "warhammer-mechanicus-0e4b71",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [
                            {
                                "pageSlug": "warhammer-mechanicus-0e4b71",
                                "pageType": "productHome",
                            }
                        ],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 0,
                                "originalPrice": 2999,
                                "voucherDiscount": 0,
                                "discount": 2999,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€29.99",
                                    "discountPrice": "0",
                                    "intermediatePrice": "0",
                                },
                            },
                            "lineOffers": [
                                {
                                    "appliedRules": [
                                        {
                                            "id": "7a3ee39632f5458990b6a9ad295881b8",
                                            "endDate": "2022-11-03T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE"
                                            },
                                        }
                                    ]
                                }
                            ],
                        },
                        "promotions": {
                            "promotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2022-10-27T15:00:00.000Z",
                                            "endDate": "2022-11-03T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 0,
                                            },
                                        }
                                    ]
                                }
                            ],
                            "upcomingPromotionalOffers": [],
                        },
                    },
                    {
                        "title": "Fallout 3: Game of the Year Edition",
                        "id": "d6f01b1827c64ed388191ae507fe7c1b",
                        "namespace": "fa702d34a37248ba98fb17f680c085e3",
                        "description": "Prepare for the Future™\nExperience the most acclaimed game of 2008 like never before with Fallout 3: Game of the Year Edition. Create a character of your choosing and descend into a post-apocalyptic world where every minute is a fight for survival",
                        "effectiveDate": "2022-10-20T15:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/offer/fa702d34a37248ba98fb17f680c085e3/EGS_Fallout3GameoftheYearEdition_BethesdaGameStudios_S2_1200x1600-e2ba392652a1f57c4feb65d6bbd1f963",
                            },
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/offer/fa702d34a37248ba98fb17f680c085e3/EGS_Fallout3GameoftheYearEdition_BethesdaGameStudios_S1_2560x1440-073f5b4cf358f437a052a3c29806efa0",
                            },
                            {
                                "type": "ProductLogo",
                                "url": "https://cdn1.epicgames.com/offer/fa702d34a37248ba98fb17f680c085e3/EGS_Fallout3GameoftheYearEdition_BethesdaGameStudios_IC1_400x400-5e37dfe1d35c9ccf25c8889fe7218613",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/offer/fa702d34a37248ba98fb17f680c085e3/EGS_Fallout3GameoftheYearEdition_BethesdaGameStudios_S2_1200x1600-e2ba392652a1f57c4feb65d6bbd1f963",
                            },
                        ],
                        "seller": {
                            "id": "o-bthbhn6wd7fzj73v5p4436ucn3k37u",
                            "name": "Bethesda Softworks LLC",
                        },
                        "productSlug": "fallout-3-game-of-the-year-edition",
                        "urlSlug": "fallout-3-game-of-the-year-edition",
                        "url": None,
                        "items": [
                            {
                                "id": "6b750e631e414927bde5b3e13b647443",
                                "namespace": "fa702d34a37248ba98fb17f680c085e3",
                            }
                        ],
                        "customAttributes": [
                            {"key": "com.epicgames.app.blacklist", "value": "[]"},
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "fallout-3-game-of-the-year-edition",
                            },
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "games/edition"},
                            {"path": "games/edition/base"},
                            {"path": "applications"},
                        ],
                        "tags": [
                            {"id": "21122"},
                            {"id": "1188"},
                            {"id": "21894"},
                            {"id": "21127"},
                            {"id": "9547"},
                            {"id": "21137"},
                            {"id": "21138"},
                            {"id": "21139"},
                            {"id": "21140"},
                            {"id": "21141"},
                            {"id": "1367"},
                            {"id": "1370"},
                            {"id": "1307"},
                            {"id": "21147"},
                            {"id": "21148"},
                            {"id": "1117"},
                            {"id": "21149"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "fallout-3-game-of-the-year-edition",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 659,
                                "originalPrice": 1999,
                                "voucherDiscount": 0,
                                "discount": 1340,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€19.99",
                                    "discountPrice": "€6.59",
                                    "intermediatePrice": "€6.59",
                                },
                            },
                            "lineOffers": [
                                {
                                    "appliedRules": [
                                        {
                                            "id": "779554ee7a604b0091a4335a60b6e55a",
                                            "endDate": "2022-11-01T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE"
                                            },
                                        }
                                    ]
                                }
                            ],
                        },
                        "promotions": {
                            "promotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2022-10-27T15:00:00.000Z",
                                            "endDate": "2022-11-01T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 33,
                                            },
                                        }
                                    ]
                                }
                            ],
                            "upcomingPromotionalOffers": [],
                        },
                    },
                    {
                        "title": "Evoland Legendary Edition",
                        "id": "e068e168886a4a90a4e36a310e3bda32",
                        "namespace": "3f7bd21610f743e598fa8e955500f5b7",
                        "description": "Evoland Legendary Edition brings you two great and unique RPGs, with their graphic style and gameplay changing as you progress through the game!",
                        "effectiveDate": "2022-10-20T15:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/spt-assets/aafde465b31e4bd5a169ff1c8a164a17/evoland-legendary-edition-1y7m0.png",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/spt-assets/aafde465b31e4bd5a169ff1c8a164a17/evoland-legendary-edition-1j93v.png",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/spt-assets/aafde465b31e4bd5a169ff1c8a164a17/evoland-legendary-edition-1j93v.png",
                            },
                        ],
                        "seller": {
                            "id": "o-ealhln64lfep9ww929uq9qcdmbyfn4",
                            "name": "Shiro Games SAS",
                        },
                        "productSlug": None,
                        "urlSlug": "224c60bb93864e1c8a1900bcf7d661dd",
                        "url": None,
                        "items": [
                            {
                                "id": "c829f27d0ab0406db8edf2b97562ee93",
                                "namespace": "3f7bd21610f743e598fa8e955500f5b7",
                            }
                        ],
                        "customAttributes": [
                            {"key": "autoGeneratedPrice", "value": "false"},
                            {"key": "isManuallySetPCReleaseDate", "value": "true"},
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games/edition"},
                            {"path": "games"},
                            {"path": "games/edition/base"},
                        ],
                        "tags": [
                            {"id": "1216"},
                            {"id": "21109"},
                            {"id": "1367"},
                            {"id": "1370"},
                            {"id": "9547"},
                            {"id": "1117"},
                            {"id": "9549"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "evoland-legendary-edition-5753ec",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [
                            {
                                "pageSlug": "evoland-legendary-edition-5753ec",
                                "pageType": "productHome",
                            }
                        ],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 1999,
                                "originalPrice": 1999,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€19.99",
                                    "discountPrice": "€19.99",
                                    "intermediatePrice": "€19.99",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": None,
                    },
                    {
                        "title": "Saturnalia",
                        "id": "275d5915ebd2479f983f51025b22a1b8",
                        "namespace": "c749cd78da34408d8434a46271f4bb79",
                        "description": "A Survival Horror Adventure: as an ensemble cast, explore an isolated village of ancient ritual – its labyrinthine roads change each time you lose all your characters.",
                        "effectiveDate": "2022-10-27T15:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "CodeRedemption_340x440",
                                "url": "https://cdn1.epicgames.com/offer/c749cd78da34408d8434a46271f4bb79/EGS_Saturnalia_SantaRagione_S4_1200x1600-2216ff4aa6997dfb13d8bd4c6f2fa99e",
                            },
                            {
                                "type": "DieselStoreFrontTall",
                                "url": "https://cdn1.epicgames.com/offer/c749cd78da34408d8434a46271f4bb79/EGS_Saturnalia_SantaRagione_S4_1200x1600-2216ff4aa6997dfb13d8bd4c6f2fa99e",
                            },
                            {
                                "type": "DieselStoreFrontWide",
                                "url": "https://cdn1.epicgames.com/offer/c749cd78da34408d8434a46271f4bb79/EGS_Saturnalia_SantaRagione_S3_2560x1440-3cd916a7260b77c8488f8f2b0f3a51ab",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/offer/c749cd78da34408d8434a46271f4bb79/EGS_Saturnalia_SantaRagione_S4_1200x1600-2216ff4aa6997dfb13d8bd4c6f2fa99e",
                            },
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/offer/c749cd78da34408d8434a46271f4bb79/EGS_Saturnalia_SantaRagione_S3_2560x1440-3cd916a7260b77c8488f8f2b0f3a51ab",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/offer/c749cd78da34408d8434a46271f4bb79/EGS_Saturnalia_SantaRagione_S4_1200x1600-2216ff4aa6997dfb13d8bd4c6f2fa99e",
                            },
                        ],
                        "seller": {
                            "id": "o-cjwnkas5rn476tzk72fbh2ftutnc2y",
                            "name": "Santa Ragione",
                        },
                        "productSlug": "saturnalia",
                        "urlSlug": "saturnalia",
                        "url": None,
                        "items": [
                            {
                                "id": "dbce8ecb6923490c9404529651251216",
                                "namespace": "c749cd78da34408d8434a46271f4bb79",
                            }
                        ],
                        "customAttributes": [
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "saturnalia",
                            }
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "games/edition/base"},
                            {"path": "games/edition"},
                            {"path": "applications"},
                        ],
                        "tags": [
                            {"id": "1218"},
                            {"id": "19847"},
                            {"id": "1080"},
                            {"id": "1370"},
                            {"id": "9547"},
                            {"id": "1117"},
                            {"id": "10719"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {"pageSlug": "saturnalia", "pageType": "productHome"}
                            ]
                        },
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 0,
                                "originalPrice": 1999,
                                "voucherDiscount": 0,
                                "discount": 1999,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "€19.99",
                                    "discountPrice": "0",
                                    "intermediatePrice": "0",
                                },
                            },
                            "lineOffers": [
                                {
                                    "appliedRules": [
                                        {
                                            "id": "8fa8f62eac9e4cab9fe242987c0f0988",
                                            "endDate": "2022-11-03T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE"
                                            },
                                        }
                                    ]
                                }
                            ],
                        },
                        "promotions": {
                            "promotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2022-10-27T15:00:00.000Z",
                                            "endDate": "2022-11-03T15:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 0,
                                            },
                                        }
                                    ]
                                }
                            ],
                            "upcomingPromotionalOffers": [],
                        },
                    },
                    {
                        "title": "Maneater",
                        "id": "a22a7af179c54b86a93f3193ace8f7f4",
                        "namespace": "d5241c76f178492ea1540fce45616757",
                        "description": "Maneater",
                        "effectiveDate": "2099-01-01T00:00:00.000Z",
                        "offerType": "OTHERS",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": True,
                        "keyImages": [
                            {
                                "type": "VaultClosed",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-tease-generic-promo-1920x1080_1920x1080-f7742c265e217510835ed14e04c48b4b",
                            },
                            {
                                "type": "DieselStoreFrontTall",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-tease-generic-promo-1920x1080_1920x1080-f7742c265e217510835ed14e04c48b4b",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-carousel-mobile-thumbnail-1200x1600_1200x1600-1f45bf1ceb21c1ca2947f6df5ece5346",
                            },
                            {
                                "type": "VaultOpened",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-w4-1920x1080_1920x1080-2df36fe63c18ff6fcb5febf3dd7ed06e",
                            },
                            {
                                "type": "DieselStoreFrontWide",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-w4-1920x1080_1920x1080-2df36fe63c18ff6fcb5febf3dd7ed06e",
                            },
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-w4-1920x1080_1920x1080-2df36fe63c18ff6fcb5febf3dd7ed06e",
                            },
                        ],
                        "seller": {
                            "id": "o-ufmrk5furrrxgsp5tdngefzt5rxdcn",
                            "name": "Epic Dev Test Account",
                        },
                        "productSlug": "maneater",
                        "urlSlug": "game-4",
                        "url": None,
                        "items": [
                            {
                                "id": "8341d7c7e4534db7848cc428aa4cbe5a",
                                "namespace": "d5241c76f178492ea1540fce45616757",
                            }
                        ],
                        "customAttributes": [
                            {
                                "key": "com.epicgames.app.freegames.vault.close",
                                "value": "[]",
                            },
                            {
                                "key": "com.epicgames.app.freegames.vault.slug",
                                "value": "free-games",
                            },
                            {
                                "key": "com.epicgames.app.freegames.vault.open",
                                "value": "[]",
                            },
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "maneater",
                            },
                        ],
                        "categories": [
                            {"path": "freegames/vaulted"},
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "applications"},
                        ],
                        "tags": [],
                        "catalogNs": {"mappings": []},
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 0,
                                "originalPrice": 0,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "0",
                                    "discountPrice": "0",
                                    "intermediatePrice": "0",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": None,
                    },
                    {
                        "title": "Wolfenstein: The New Order",
                        "id": "1d41b93230e54bdd80c559d72adb7f4f",
                        "namespace": "d5241c76f178492ea1540fce45616757",
                        "description": "Wolfenstein: The New Order",
                        "effectiveDate": "2099-01-01T00:00:00.000Z",
                        "offerType": "OTHERS",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": True,
                        "keyImages": [
                            {
                                "type": "VaultClosed",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-tease-generic-promo-1920x1080_1920x1080-f7742c265e217510835ed14e04c48b4b",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-carousel-mobile-thumbnail-1200x1600_1200x1600-1f45bf1ceb21c1ca2947f6df5ece5346",
                            },
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-w3-1920x1080_1920x1080-4a501d33fb4ac641e3e1e290dcc0e6c1",
                            },
                            {
                                "type": "DieselStoreFrontWide",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-w3-1920x1080_1920x1080-4a501d33fb4ac641e3e1e290dcc0e6c1",
                            },
                            {
                                "type": "VaultOpened",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/egs-vault-w3-1920x1080_1920x1080-4a501d33fb4ac641e3e1e290dcc0e6c1",
                            },
                        ],
                        "seller": {
                            "id": "o-ufmrk5furrrxgsp5tdngefzt5rxdcn",
                            "name": "Epic Dev Test Account",
                        },
                        "productSlug": "wolfenstein-the-new-order",
                        "urlSlug": "game-3",
                        "url": None,
                        "items": [
                            {
                                "id": "8341d7c7e4534db7848cc428aa4cbe5a",
                                "namespace": "d5241c76f178492ea1540fce45616757",
                            }
                        ],
                        "customAttributes": [
                            {
                                "key": "com.epicgames.app.freegames.vault.close",
                                "value": "[]",
                            },
                            {
                                "key": "com.epicgames.app.freegames.vault.slug",
                                "value": "free-games",
                            },
                            {
                                "key": "com.epicgames.app.freegames.vault.open",
                                "value": "[]",
                            },
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "wolfenstein-the-new-order",
                            },
                        ],
                        "categories": [
                            {"path": "freegames/vaulted"},
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "applications"},
                        ],
                        "tags": [],
                        "catalogNs": {"mappings": []},
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 0,
                                "originalPrice": 0,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "0",
                                    "discountPrice": "0",
                                    "intermediatePrice": "0",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": None,
                    },
                ],
                "paging": {"count": 1000, "total": 14},
            }
        }
    },
    "extensions": {},
}

DATA_ONE_FREE_GAME = {
    "data": {
        "Catalog": {
            "searchStore": {
                "elements": [
                    {
                        "title": "Borderlands 3 Season Pass",
                        "id": "c3913a91e07b43cfbbbcfd8244c86dcc",
                        "namespace": "catnip",
                        "description": "Prolongez votre aventure dans Borderlands\xa03 avec le Season Pass, regroupant des éléments cosmétiques exclusifs et quatre histoires additionnelles, pour encore plus de missions et de défis\xa0!",
                        "effectiveDate": "2019-09-11T12:00:00.000Z",
                        "offerType": "DLC",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/offer/catnip/Diesel_productv2_borderlands-3_season-pass_BL3_SEASONPASS_Hero-3840x2160-4411e63a005a43811a2bc516ae7ec584598fd4aa-3840x2160-b8988ebb0f3d9159671e8968af991f30_3840x2160-b8988ebb0f3d9159671e8968af991f30",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/offer/catnip/2KGMKT_BL3_Season_Pass_EGS_1200x1600_1200x1600-a7438a079c5576d328a74b9121278075",
                            },
                            {
                                "type": "CodeRedemption_340x440",
                                "url": "https://cdn1.epicgames.com/offer/catnip/2KGMKT_BL3_Season_Pass_EGS_1200x1600_1200x1600-a7438a079c5576d328a74b9121278075",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/offer/catnip/2KGMKT_BL3_Season_Pass_EGS_1200x1600_1200x1600-a7438a079c5576d328a74b9121278075",
                            },
                        ],
                        "seller": {
                            "id": "o-37m6jbj5wcvrcvm4wusv7nazdfvbjk",
                            "name": "2K Games, Inc.",
                        },
                        "productSlug": "borderlands-3/season-pass",
                        "urlSlug": "borderlands-3--season-pass",
                        "url": None,
                        "items": [
                            {
                                "id": "e9fdc1a9f47b4a5e8e63841c15de2b12",
                                "namespace": "catnip",
                            },
                            {
                                "id": "fbc46bb6056940d2847ee1e80037a9af",
                                "namespace": "catnip",
                            },
                            {
                                "id": "ff8e1152ddf742b68f9ac0cecd378917",
                                "namespace": "catnip",
                            },
                            {
                                "id": "939e660825764e208938ab4f26b4da56",
                                "namespace": "catnip",
                            },
                            {
                                "id": "4c43a9a691114ccd91c1884ab18f4e27",
                                "namespace": "catnip",
                            },
                            {
                                "id": "3a6a3f9b351b4b599808df3267669b83",
                                "namespace": "catnip",
                            },
                            {
                                "id": "ab030a9f53f3428fb2baf2ddbb0bb5ac",
                                "namespace": "catnip",
                            },
                            {
                                "id": "ff96eef22b0e4c498e8ed80ac0030325",
                                "namespace": "catnip",
                            },
                            {
                                "id": "5021e93a73374d6db1c1ce6c92234f8f",
                                "namespace": "catnip",
                            },
                            {
                                "id": "9c0b1eb3265340678dff0fcb106402b1",
                                "namespace": "catnip",
                            },
                            {
                                "id": "8c826db6e14f44aeac8816e1bd593632",
                                "namespace": "catnip",
                            },
                        ],
                        "customAttributes": [
                            {"key": "com.epicgames.app.blacklist", "value": "SA"},
                            {"key": "publisherName", "value": "2K"},
                            {"key": "developerName", "value": "Gearbox Software"},
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "borderlands-3/season-pass",
                            },
                        ],
                        "categories": [
                            {"path": "addons"},
                            {"path": "freegames"},
                            {"path": "addons/durable"},
                            {"path": "applications"},
                        ],
                        "tags": [
                            {"id": "1264"},
                            {"id": "16004"},
                            {"id": "14869"},
                            {"id": "26789"},
                            {"id": "1367"},
                            {"id": "1370"},
                            {"id": "9547"},
                            {"id": "9549"},
                            {"id": "1294"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {"pageSlug": "borderlands-3", "pageType": "productHome"}
                            ]
                        },
                        "offerMappings": [
                            {
                                "pageSlug": "borderlands-3--season-pass",
                                "pageType": "addon--cms-hybrid",
                            }
                        ],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 4999,
                                "originalPrice": 4999,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "49,99\xa0€",
                                    "discountPrice": "49,99\xa0€",
                                    "intermediatePrice": "49,99\xa0€",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": {
                            "promotionalOffers": [],
                            "upcomingPromotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2023-03-09T16:00:00.000Z",
                                            "endDate": "2023-03-16T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 30,
                                            },
                                        },
                                        {
                                            "startDate": "2023-03-09T16:00:00.000Z",
                                            "endDate": "2023-03-16T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 25,
                                            },
                                        },
                                        {
                                            "startDate": "2023-03-09T16:00:00.000Z",
                                            "endDate": "2023-03-16T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 25,
                                            },
                                        },
                                        {
                                            "startDate": "2023-03-09T16:00:00.000Z",
                                            "endDate": "2023-03-16T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 30,
                                            },
                                        },
                                    ]
                                }
                            ],
                        },
                    },
                    {
                        "title": "Call of the Sea",
                        "id": "92da5d8d918543b6b408e36d9af81765",
                        "namespace": "5e427319eea1401ab20c6cd78a4163c4",
                        "description": "Call of the Sea is an otherworldly tale of mystery and love set in the 1930s South Pacific. Explore a lush island paradise, solve puzzles and unlock secrets in the hunt for your husband’s missing expedition.",
                        "effectiveDate": "2022-02-17T15:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "DieselStoreFrontWide",
                                "url": "https://cdn1.epicgames.com/salesEvent/salesEvent/EGS_CalloftheSea_OutoftheBlue_S1_2560x1440-204699c6410deef9c18be0ee392f8335",
                            },
                            {
                                "type": "DieselStoreFrontTall",
                                "url": "https://cdn1.epicgames.com/salesEvent/salesEvent/EGS_CalloftheSea_OutoftheBlue_S2_1200x1600-db63acf0c479c185e0ef8f8e73c8f0d8",
                            },
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/salesEvent/salesEvent/EGS_CalloftheSea_OutoftheBlue_S5_1920x1080-7b22dfebdd9fcdde6e526c5dc4c16eb1",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/salesEvent/salesEvent/EGS_CalloftheSea_OutoftheBlue_S2_1200x1600-db63acf0c479c185e0ef8f8e73c8f0d8",
                            },
                            {
                                "type": "CodeRedemption_340x440",
                                "url": "https://cdn1.epicgames.com/salesEvent/salesEvent/EGS_CalloftheSea_OutoftheBlue_S2_1200x1600-db63acf0c479c185e0ef8f8e73c8f0d8",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/salesEvent/salesEvent/EGS_CalloftheSea_OutoftheBlue_S2_1200x1600-db63acf0c479c185e0ef8f8e73c8f0d8",
                            },
                        ],
                        "seller": {
                            "id": "o-fay4ghw9hhamujs53rfhy83ffexb7k",
                            "name": "Raw Fury",
                        },
                        "productSlug": "call-of-the-sea",
                        "urlSlug": "call-of-the-sea",
                        "url": None,
                        "items": [
                            {
                                "id": "cbc9c76c4bfc4bc6b28abb3afbcbf07a",
                                "namespace": "5e427319eea1401ab20c6cd78a4163c4",
                            }
                        ],
                        "customAttributes": [
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "call-of-the-sea",
                            }
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "games/edition"},
                            {"path": "games/edition/base"},
                            {"path": "applications"},
                        ],
                        "tags": [
                            {"id": "1296"},
                            {"id": "1298"},
                            {"id": "21894"},
                            {"id": "1370"},
                            {"id": "9547"},
                            {"id": "1117"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "call-of-the-sea",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 1999,
                                "originalPrice": 1999,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "19,99\xa0€",
                                    "discountPrice": "19,99\xa0€",
                                    "intermediatePrice": "19,99\xa0€",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": {
                            "promotionalOffers": [],
                            "upcomingPromotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2023-03-09T16:00:00.000Z",
                                            "endDate": "2023-03-16T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 60,
                                            },
                                        },
                                        {
                                            "startDate": "2023-03-09T16:00:00.000Z",
                                            "endDate": "2023-03-16T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 0,
                                            },
                                        },
                                        {
                                            "startDate": "2023-03-09T16:00:00.000Z",
                                            "endDate": "2023-03-16T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 60,
                                            },
                                        },
                                    ]
                                }
                            ],
                        },
                    },
                    {
                        "title": "Rise of Industry",
                        "id": "c04a2ab8ff4442cba0a41fb83453e701",
                        "namespace": "9f101e25b1a9427a9e6971d2b21c5f82",
                        "description": "Mettez vos compétences entrepreneuriales à l'épreuve en créant et en optimisant des chaînes de production complexes tout en gardant un œil sur les résultats financiers. À l'aube du 20e siècle, apprêtez-vous à entrer dans un âge d'or industriel, ou une dépression historique.",
                        "effectiveDate": "2022-08-11T11:00:00.000Z",
                        "offerType": "BASE_GAME",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": False,
                        "keyImages": [
                            {
                                "type": "OfferImageWide",
                                "url": "https://cdn1.epicgames.com/spt-assets/a6aeec29591b4b56b4383b4d2d7d0e1e/rise-of-industry-offer-1p22f.jpg",
                            },
                            {
                                "type": "OfferImageTall",
                                "url": "https://cdn1.epicgames.com/spt-assets/a6aeec29591b4b56b4383b4d2d7d0e1e/download-rise-of-industry-offer-1uujr.jpg",
                            },
                            {
                                "type": "Thumbnail",
                                "url": "https://cdn1.epicgames.com/spt-assets/a6aeec29591b4b56b4383b4d2d7d0e1e/download-rise-of-industry-offer-1uujr.jpg",
                            },
                        ],
                        "seller": {
                            "id": "o-fnqgc5v2xczx9fgawvcejwj88z2mnx",
                            "name": "Kasedo Games Ltd",
                        },
                        "productSlug": None,
                        "urlSlug": "f88fedc022fe488caaedaa5c782ff90d",
                        "url": None,
                        "items": [
                            {
                                "id": "9f5b48a778824e6aa330d2c1a47f41b2",
                                "namespace": "9f101e25b1a9427a9e6971d2b21c5f82",
                            }
                        ],
                        "customAttributes": [
                            {"key": "autoGeneratedPrice", "value": "false"},
                            {"key": "isManuallySetPCReleaseDate", "value": "true"},
                        ],
                        "categories": [
                            {"path": "freegames"},
                            {"path": "games/edition/base"},
                            {"path": "games/edition"},
                            {"path": "games"},
                        ],
                        "tags": [
                            {"id": "26789"},
                            {"id": "19847"},
                            {"id": "1370"},
                            {"id": "1115"},
                            {"id": "9547"},
                            {"id": "10719"},
                        ],
                        "catalogNs": {
                            "mappings": [
                                {
                                    "pageSlug": "rise-of-industry-0af838",
                                    "pageType": "productHome",
                                }
                            ]
                        },
                        "offerMappings": [
                            {
                                "pageSlug": "rise-of-industry-0af838",
                                "pageType": "productHome",
                            }
                        ],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 0,
                                "originalPrice": 2999,
                                "voucherDiscount": 0,
                                "discount": 2999,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "29,99\xa0€",
                                    "discountPrice": "0",
                                    "intermediatePrice": "0",
                                },
                            },
                            "lineOffers": [
                                {
                                    "appliedRules": [
                                        {
                                            "id": "a19d30dc34f44923993e68b82b75a084",
                                            "endDate": "2023-03-09T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE"
                                            },
                                        }
                                    ]
                                }
                            ],
                        },
                        "promotions": {
                            "promotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2023-03-02T16:00:00.000Z",
                                            "endDate": "2023-03-09T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 0,
                                            },
                                        }
                                    ]
                                }
                            ],
                            "upcomingPromotionalOffers": [
                                {
                                    "promotionalOffers": [
                                        {
                                            "startDate": "2023-03-09T16:00:00.000Z",
                                            "endDate": "2023-03-16T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 25,
                                            },
                                        },
                                        {
                                            "startDate": "2023-03-09T16:00:00.000Z",
                                            "endDate": "2023-03-16T16:00:00.000Z",
                                            "discountSetting": {
                                                "discountType": "PERCENTAGE",
                                                "discountPercentage": 25,
                                            },
                                        },
                                    ]
                                }
                            ],
                        },
                    },
                    {
                        "title": "Dishonored - Definitive Edition",
                        "id": "4d25d74b88d1474a8ab21ffb88ca6d37",
                        "namespace": "d5241c76f178492ea1540fce45616757",
                        "description": "Experience the definitive Dishonored collection. This complete compilation includes Dishonored as well as all of its additional content - Dunwall City Trials, The Knife of Dunwall, The Brigmore Witches and Void Walker’s Arsenal.",
                        "effectiveDate": "2099-01-01T00:00:00.000Z",
                        "offerType": "OTHERS",
                        "expiryDate": None,
                        "status": "ACTIVE",
                        "isCodeRedemptionOnly": True,
                        "keyImages": [
                            {
                                "type": "VaultClosed",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/15days-day15-wrapped-desktop-carousel-image_1920x1080-ebecfa7c79f02a9de5bca79560bee953",
                            },
                            {
                                "type": "DieselStoreFrontWide",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/15days-day15-Unwrapped-desktop-carousel-image1_1920x1080-1992edb42bb8554ddeb14d430ba3f858",
                            },
                            {
                                "type": "DieselStoreFrontTall",
                                "url": "https://cdn1.epicgames.com/offer/d5241c76f178492ea1540fce45616757/DAY15-carousel-mobile-unwrapped-image1_1200x1600-9716d77667d2a82931c55a4e4130989e",
                            },
                        ],
                        "seller": {
                            "id": "o-ufmrk5furrrxgsp5tdngefzt5rxdcn",
                            "name": "Epic Dev Test Account",
                        },
                        "productSlug": "dishonored-definitive-edition",
                        "urlSlug": "mystery-game15",
                        "url": None,
                        "items": [
                            {
                                "id": "8341d7c7e4534db7848cc428aa4cbe5a",
                                "namespace": "d5241c76f178492ea1540fce45616757",
                            }
                        ],
                        "customAttributes": [
                            {
                                "key": "com.epicgames.app.freegames.vault.close",
                                "value": "[]",
                            },
                            {
                                "key": "com.epicgames.app.freegames.vault.slug",
                                "value": "sales-and-specials/holiday-sale",
                            },
                            {"key": "com.epicgames.app.blacklist", "value": "[]"},
                            {
                                "key": "com.epicgames.app.freegames.vault.open",
                                "value": "[]",
                            },
                            {
                                "key": "com.epicgames.app.productSlug",
                                "value": "dishonored-definitive-edition",
                            },
                        ],
                        "categories": [
                            {"path": "freegames/vaulted"},
                            {"path": "freegames"},
                            {"path": "games"},
                            {"path": "applications"},
                        ],
                        "tags": [],
                        "catalogNs": {"mappings": []},
                        "offerMappings": [],
                        "price": {
                            "totalPrice": {
                                "discountPrice": 0,
                                "originalPrice": 0,
                                "voucherDiscount": 0,
                                "discount": 0,
                                "currencyCode": "EUR",
                                "currencyInfo": {"decimals": 2},
                                "fmtPrice": {
                                    "originalPrice": "0",
                                    "discountPrice": "0",
                                    "intermediatePrice": "0",
                                },
                            },
                            "lineOffers": [{"appliedRules": []}],
                        },
                        "promotions": None,
                    },
                ],
                "paging": {"count": 1000, "total": 4},
            }
        }
    },
    "extensions": {},
}
