"""Typing for data used by VRChat API."""

from typing import Any, TypedDict

### User ###


class AccountDeletionLog(TypedDict):
    """Sub return data type of `get_current_user`."""

    message: str
    deletionScheduled: str
    dateTime: str


class Badges(TypedDict):
    """Sub return data type of `get_current_user`."""

    assignedAt: str
    badgeDescription: str
    badgeId: str
    badgeImageUrl: str
    badgeName: str
    hidden: bool
    showcased: bool
    updatedAt: str


class DiscordDetails(TypedDict):
    """Sub return data type of `get_current_user`."""

    global_name: str
    id: str


class PastDisplayNames(TypedDict):
    """Sub return data type of `get_current_user`."""

    displayName: str
    updated_at: str


class Presence(TypedDict):
    """Sub return data type of `get_current_user`."""

    avatarThumbnail: str
    currentAvatarTags: list[str]
    displayName: str
    debugflag: str
    groups: list[str]
    id: str
    instance: str
    instanceType: str
    isRejoining: str
    platform: str
    profilePicOverride: str
    status: str
    travelingToInstance: str
    travelingToWorld: str
    userIcon: str
    world: str


class PlatformHistory(TypedDict):
    """Sub return data type of `get_current_user`."""

    isMobile: bool
    platform: str
    recorded: str


class SteamDetails(TypedDict):
    """Sub return data type of `get_current_user`."""

    avatar: str
    avatarfull: str
    avatarhash: str
    avatarmedium: str
    communityvisibilitystate: int
    gameextrainfo: str
    gameid: str
    personaname: str
    personastate: int
    personastateflags: int
    primaryclanid: str
    profilestate: int
    profileurl: str
    steamid: str
    timecreated: int


class CurrentUser(TypedDict):
    """Return data type of `get_current_user`."""

    acceptedTOSVersion: int
    acceptedPrivacyVersion: int
    accountDeletionDate: str
    accountDeletionLog: list[AccountDeletionLog]
    activeFriends: list[str]
    ageVerificationStatus: str
    ageVerified: bool
    allowAvatarCopying: bool
    appleId: str
    appleDetails: dict
    authToken: str
    badges: list[Badges]
    bio: str
    bioLinks: list[str]
    contentFilters: list[str]
    currentAvatar: str
    currentAvatarImageUrl: str
    currentAvatarThumbnailImageUrl: str
    currentAvatarTags: list[str]
    date_joined: str
    developerType: str
    discordDetails: DiscordDetails
    discordId: str
    displayName: str
    emailVerified: bool
    fallbackAvatar: str
    friendGroupNames: list[str]
    friendKey: str
    friends: list[str]
    hasBirthday: bool
    hideContentFilterSettings: bool
    userLanguage: str
    userLanguageCode: str
    hasEmail: bool
    hasLoggedInFromClient: bool
    hasPendingEmail: bool
    homeLocation: str
    id: str
    imageUrl: str
    isAdult: bool
    isBoopingEnabled: bool
    isFriend: bool
    last_activity: str
    last_login: str
    last_mobile: str
    last_platform: str
    obfuscatedEmail: str
    obfuscatedPendingEmail: str
    oculusId: str
    googleId: str
    googleDetails: dict
    picoId: str
    viveId: str
    offlineFriends: list[str]
    onlineFriends: list[str]
    pastDisplayNames: list[PastDisplayNames]
    presence: Presence
    platform_history: list[PlatformHistory]
    profilePicOverride: str
    profilePicOverrideThumbnail: str
    pronouns: str
    pronounsHistory: list[str]
    queuedInstance: str
    receiveMobileInvitations: bool
    state: str
    status: str
    statusDescription: str
    statusFirstTime: bool
    statusHistory: list[str]
    steamDetails: SteamDetails
    steamId: str
    tags: list[str]
    twoFactorAuthEnabled: bool
    twoFactorAuthEnabledDate: str
    unsubscribe: bool
    updated_at: str
    userIcon: str
    username: str


class User(TypedDict, total=False):
    """User data."""

    ageVerificationStatus: str
    ageVerified: bool
    allowAvatarCopying: bool
    badges: list[Badges]
    bio: str
    bioLinks: list[str]
    currentAvatarImageUrl: str
    currentAvatarThumbnailImageUrl: str
    currentAvatarTags: list[str]
    date_joined: str
    developerType: str
    displayName: str
    friendKey: str
    friend_of: str
    friendRequestStatus: str
    id: str
    imageUrl: str
    instanceId: str
    isFriend: bool
    last_activity: str
    last_login: str
    last_mobile: str
    last_platform: str
    location: str
    note: str
    platform: str
    profilePicOverride: str
    profilePicOverrideThumbnail: str
    presence: dict[str, Any]
    pronouns: str
    state: str
    status: str
    statusDescription: str
    tags: list[str]
    travelingToInstance: str
    travelingToLocation: str
    travelingToWorld: str
    userIcon: str
    username: str
    worldId: str


class WebsocketUserEvent(TypedDict):
    """User related websocket event data."""

    type: str
    content: WebsocketUserEventContent


class WebsocketUserEventContent(TypedDict, total=False):
    """User related websocket event data content."""

    userId: str
    user: User
    world: World


### World ###


class DefaultContentSettings(TypedDict):
    """VRChat world default content settings."""

    drones: bool
    emoji: bool
    pedestals: bool
    prints: bool
    props: bool
    stickers: bool


class World(TypedDict):
    """VRChat world."""

    authorId: str
    authorName: str
    capacity: int
    created_at: str
    defaultContentSettings: DefaultContentSettings
    description: str
    favorites: int
    featured: bool
    heat: int
    id: str
    imageUrl: str
    labsPublicationDate: str
    name: str
    namespace: str
    occupants: int
    organization: str
    popularity: int
    previewYoutubeId: str
    privateOccupants: int
    publicOccupants: int
    publicationDate: str
    recommendedCapacity: int
    releaseStatus: str
    storeId: str
    tags: list[str]
    thumbnailImageUrl: str
    udonProducts: list[str]
    updated_at: str
    urlList: list[str]
    version: int
    visits: int
