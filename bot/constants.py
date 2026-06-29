# constants.py
import hashlib
import uuid

# =============================================================================
# CONNECTION CONFIGURATION
# =============================================================================

HABBO_HOST = "game-us.habbo.com"
HABBO_PORT = 30000
TIMEOUT = 10

# Files
ACCOUNTS_FILE = "accounts.json"

# =============================================================================
# MULTI-HOTEL REGISTRY
# =============================================================================
# Añade aquí cualquier hotel activo. Formato: dominio → config de conexión.

HOTELS = {
    'habbo.com': {
        'name':     'Habbo.com (International)',
        'host':     'game-us.habbo.com',
        'port':     30000,
        'base_url': 'https://www.habbo.com',
        'ext_vars': 'https://www.habbo.com/gamedata/external_variables/1',
    },
    'habbo.com.tr': {
        'name':     'Habbo.com.tr (Turkey)',
        'host':     'game-tr.habbo.com',
        'port':     30000,
        'base_url': 'https://www.habbo.com.tr',
        'ext_vars': 'https://www.habbo.com.tr/gamedata/external_variables/1',
    },
    'habbo.com.br': {
        'name':     'Habbo.com.br (Brazil)',
        'host':     'game-br.habbo.com',
        'port':     30000,
        'base_url': 'https://www.habbo.com.br',
        'ext_vars': 'https://www.habbo.com.br/gamedata/external_variables/1',
    },
    'habbo.es': {
        'name':     'Habbo.es (Spain)',
        'host':     'game-es.habbo.com',
        'port':     30000,
        'base_url': 'https://www.habbo.es',
        'ext_vars': 'https://www.habbo.es/gamedata/external_variables/1',
    },
    'habbo.de': {
        'name':     'Habbo.de (Germany)',
        'host':     'game-de.habbo.com',
        'port':     30000,
        'base_url': 'https://www.habbo.de',
        'ext_vars': 'https://www.habbo.de/gamedata/external_variables/1',
    },
    'habbo.fi': {
        'name':     'Habbo.fi (Finland)',
        'host':     'game-fi.habbo.com',
        'port':     30000,
        'base_url': 'https://www.habbo.fi',
        'ext_vars': 'https://www.habbo.fi/gamedata/external_variables/1',
    },
    'habbo.it': {
        'name':     'Habbo.it (Italy)',
        'host':     'game-it.habbo.com',
        'port':     30000,
        'base_url': 'https://www.habbo.it',
        'ext_vars': 'https://www.habbo.it/gamedata/external_variables/1',
    },
    'habbo.nl': {
        'name':     'Habbo.nl (Netherlands)',
        'host':     'game-nl.habbo.com',
        'port':     30000,
        'base_url': 'https://www.habbo.nl',
        'ext_vars': 'https://www.habbo.nl/gamedata/external_variables/1',
    },
    'habbo.fr': {
        'name':     'Habbo.fr (France)',
        'host':     'game-fr.habbo.com',
        'port':     30000,
        'base_url': 'https://www.habbo.fr',
        'ext_vars': 'https://www.habbo.fr/gamedata/external_variables/1',
    },
}

DEFAULT_HOTEL = 'habbo.com'

# =============================================================================
# CLIENT IDENTIFICATION & FINGERPRINTING
# Actualizado automáticamente por fetch_and_apply_latest_headers()
# Valores base: WIN63-202606011215-150448581 / FLASH28
# =============================================================================

RELEASE_VERSION = "WIN63-202606011215-150448581"
CLIENT_TYPE     = "FLASH28"
PLATFORM_ID     = 6
CLIENT_VERSION  = 4
EXTERNAL_VARIABLES_URL = "https://www.habbo.com/gamedata/external_variables/1"

STATIC_MACHINE_ID       = ""
STATIC_FINGERPRINT      = "~a239d36007e0c37b48238796aa759aa"
STATIC_PLATFORM_STRING  = "WIN/51,1,1,5"

def generate_md5_fingerprint():
    random_data = str(uuid.uuid4()).encode('utf-8')
    return f"~{hashlib.md5(random_data).hexdigest()}"

# =============================================================================
# CRYPTOGRAPHY
# =============================================================================

RSA_MODULUS_HEX = "C5DFF029848CD5CF4A84ADEFB2DA6685704920D5EBE8850B82C419A97B95302DE3B8021F37719FEBD4B3516E04D1E4702E74C468C9FF4BBBB5DD44A1E3A08687EDBEF7C30A176F7C8C83226A77F7982F7442D884D8149E924C486F43035C07B9167EA998416919DA4116D5E0598C11BA1542B4160136F04135C06EDF80170245E73C0DAD63895F52DCED3735582C5852744C8EC40AF576F26A9C8DC5B64ED3DAD40EFAAC6A76A1F5C2A422A8A4691F8991356467BDA61E1D34D0F35531058C8F741E4661ACFCB15C806A996AC312A8D33BF45079B89E11787537B37364749B883BDBFDE51A1A55086CF16159F5DEBCC76342AC2EF6950DA0C70C5845C97DFD49"
RSA_EXPONENT_HEX = "10001"

# =============================================================================
# GAME DATA (FIGURES & ADMINS)
# =============================================================================

RANDOM_FIGURES_MALE = [
    "ch-255-64.hr-893-31.sh-3068-64-1408.lg-3088-64-1408.hd-208-10",
    "ha-1018-0.sh-305-64.lg-3023-64.hd-180-1.ch-225-88.hr-155-40.cc-3294-88-88",
    "ha-1020-0.sh-3115-64-1408.lg-3078-1408.hd-209-1370.ch-255-90.hr-125-31.ca-1804-73",
    "ch-809-83.hr-110-44.sh-300-64.lg-270-84.hd-200-30",
    "ha-1013-1408.sh-908-1408.lg-275-64.hd-209-10.ch-255-82.hr-170-31",
    "ch-255-66.hr-3090-34.sh-3068-1320-1408.lg-3023-66.hd-209-10",
    "ch-808-85.hr-125-48.lg-3078-64.hd-205-1371",
    "ha-1004-91.lg-3078-91.ea-1404-64.hd-190-19.ch-3030-71.hr-170-45.cp-3288-64.he-1608-0",
    "ea-1404-64.ch-267-64.lg-3078-1408.wa-2009-1408.sh-906-1408.hd-208-10.hr-125-42.fa-1208-91",
    "ea-1406-0.ch-210-1408.lg-3216-72.wa-3074-1320-1320.he-1610-0.ca-1802-0.sh-905-72.hd-207-10.hr-170-45.cc-3294-83-73.fa-1201-0",
    "sh-305-1408.hd-180-14.ch-267-1408.lg-280-64.hr-170-31",
    "ea-1404-64.ch-220-81.lg-285-64.sh-290-1408.hd-205-10.hr-3090-45.fa-1201-0",
    "ch-3111-82-1408.lg-285-64.sh-290-64.hd-180-1.hr-170-34.fa-1210-0",
]

RANDOM_FIGURES_FEMALE = [
    "ca-1804-83.hd-629-1.ch-685-73.lg-3216-1408.sh-907-1408.hr-890-36",
    "hd-600-1.ch-685-82.lg-3088-64-1408.he-3274-82.sh-735-82.hr-890-45",
    "hd-600-10.ch-813-82.lg-710-82.he-1602-81.fa-3276-72.sh-905-82.hr-890-34",
    "hd-629-10.sh-3068-1408-71.hr-890-31.ch-665-1408.lg-3216-74",
    "hd-615-1.ch-816-73.lg-695-64.fa-3276-73.sh-907-64.hr-681-45",
    "hd-600-10.ch-660-73.lg-720-91.fa-3276-73.sh-740-1408.hr-515-44",
    "hd-600-1.sh-3068-1408-1408.hr-545-31.ch-665-1408.lg-3216-91",
    "hd-600-1371.sh-3068-1408-1408.hr-545-31.ch-665-1408.lg-3216-91",
    "hd-600-1371.ch-665-73.lg-720-91.fa-1212-73.ea-1404-64.sh-740-1408.hr-550-44"
]

ADMINS = [
    "noodlesoup","knitty","GentleTeapot","TheWeatherFrog","Alyx_Staff",
    "Amaiazing","WaltzMatilda","sparkaro","Guaja","Truculencia","istanbul",
    "Olsoweir","Natunen","-LittleMin","PrincessTwinkle"
]

# =============================================================================
# PACKET HEADERS (OUTGOING)  —  WIN63-202606011215-150448581 / FLASH28
# =============================================================================

class Outgoing:
    # Handshake
    CLIENT_HELLO              = 4000   # ClientHelloMessageComposer
    INIT_DIFFIE_HANDSHAKE     = 2456   # InitDiffieHandshakeMessageComposer
    COMPLETE_DIFFIE_HANDSHAKE = 669    # CompleteDiffieHandshakeMessageComposer
    VERSION_CHECK             = 1148   # VersionCheckMessageComposer
    UNIQUE_ID                 = 1003   # UniqueIDMessageComposer
    SSO_TICKET                = 30     # SSOTicketMessageComposer
    INFO_RETRIEVE             = 1317   # InfoRetrieveMessageComposer
    DISCONNECT                = 268    # DisconnectMessageComposer

    # Ping / Pong
    LATENCY_PING_REQUEST      = 1673   # LatencyPingRequestMessageComposer
    PONG                      = 2058   # PongMessageComposer

    # Room Entry & Navigation
    OPEN_FLAT_CONNECTION      = 2428   # OpenFlatConnectionMessageComposer
    GET_GUEST_ROOM            = 1212   # GetGuestRoomMessageComposer
    GET_INTERSTITIAL          = 3138   # GetInterstitialMessageComposer
    QUIT_ROOM                 = 1168   # QuitMessageComposer
    SELECT_INITIAL_ROOM       = 1191   # SelectInitialRoomComposer
    UPDATE_HOME_ROOM          = 1031   # UpdateHomeRoomMessageComposer
    NEW_NAVIGATOR_INIT        = 59     # NewNavigatorInitComposer
    NEW_NAVIGATOR_SEARCH      = 66     # NewNavigatorSearchComposer

    # Movement & Posture
    MOVE_AVATAR               = 2314   # MoveAvatarMessageComposer
    LOOK_TO                   = 469    # LookToMessageComposer
    CHANGE_POSTURE            = 3010   # ChangePostureMessageComposer

    # Chat
    SHOUT                     = 43     # ShoutMessageComposer
    CHAT                      = 7      # ChatMessageComposer
    WHISPER                   = 81     # WhisperMessageComposer

    # Animations & Social
    DANCE                     = 1643   # DanceMessageComposer
    SIGN                      = 477    # SignMessageComposer
    AVATAR_EXPRESSION         = 3047   # AvatarExpressionMessageComposer
    RESPECT_USER              = 1062   # RespectUserMessageComposer
    REPLENISH_RESPECT         = 3569   # ReplenishRespectMessageComposer

    # User Profile
    CHANGE_MOTTO              = 1573   # ChangeMottoMessageComposer
    UPDATE_FIGURE             = 704    # UpdateFigureDataMessageComposer
    CHANGE_USERNAME           = 863    # ChangeUserNameMessageComposer
    CHANGE_USERNAME_IN_ROOM   = 69     # ChangeUserNameInRoomMessageComposer
    REQUEST_FRIEND            = 2486   # RequestFriendMessageComposer

    # Effects / Catalog / Economy
    AVATAR_EFFECT_ACTIVATED   = 1315   # AvatarEffectActivatedComposer
    AVATAR_EFFECT_SELECTED    = 3236   # AvatarEffectSelectedComposer
    PURCHASE_FROM_CATALOG     = 2375   # PurchaseFromCatalogComposer
    INCOME_REWARD_STATUS      = 1202   # IncomeRewardStatusMessageComposer
    INCOME_REWARD_CLAIM       = 282    # IncomeRewardClaimMessageComposer


# =============================================================================
# PACKET HEADERS (INCOMING)  —  WIN63-202606011215-150448581 / FLASH28
# =============================================================================

class Incoming:
    # Handshake
    SERVER_INIT_DIFFIE_HANDSHAKE     = 2387   # InitDiffieHandshakeEvent
    SERVER_COMPLETE_DIFFIE_HANDSHAKE = 226    # CompleteDiffieHandshakeEvent
    AUTHENTICATION_OK                = 1378   # AuthenticationOKMessageEvent
    REQUEST_MACHINE_ID               = 2865   # UniqueMachineIDEvent
    GENERIC_ERROR                    = 2239   # GenericErrorEvent
    USER_RIGHTS                      = 76     # UserRightsMessageEvent
    IS_FIRST_LOGIN_OF_DAY            = 2993   # IsFirstLoginOfDayEvent
    DISCONNECT_REASON                = 4000   # DisconnectReasonEvent

    # General
    PING                             = 591    # PingMessageEvent
    LATENCY_PING_RESPONSE            = 147    # LatencyPingResponseMessageEvent
    FLOOD_CONTROL                    = 3921   # FloodControlMessageEvent
    REMAINING_MUTE_PERIOD            = 3059   # RemainingMutePeriodEvent

    # Room Connection & Navigation
    OPEN_CONNECTION                  = 32     # OpenConnectionMessageEvent
    ROOM_READY                       = 3673   # RoomReadyMessageEvent
    ROOM_FORWARD                     = 23     # RoomForwardMessageEvent
    FLAT_ACCESS_DENIED               = 773    # FlatAccessDeniedMessageEvent
    DOORBELL                         = 1280   # DoorbellMessageEvent
    FLAT_CREATED                     = 387    # FlatCreatedEvent
    NAVIGATOR_SEARCH_RESULT_BLOCKS   = 1509   # NavigatorSearchResultBlocksEvent

    # Room Layout
    FLOOR_HEIGHT_MAP                 = 2888   # FloorHeightMapMessageEvent
    HEIGHT_MAP                       = 3413   # HeightMapMessageEvent
    ROOM_ENTRY_TILE                  = 2353   # RoomEntryTileMessageEvent

    # Users in Room
    USERS                            = 1541   # UsersMessageEvent
    USER_REMOVE                      = 3524   # UserRemoveMessageEvent
    USER_UPDATE                      = 1601   # UserUpdateMessageEvent
    USER_CHANGE                      = 1779   # UserChangeMessageEvent
    USER_TYPING                      = 978    # UserTypingMessageEvent

    # Chat
    CHAT                             = 3936   # ChatMessageEvent
    SHOUT                            = 3301   # ShoutMessageEvent
    WHISPER                          = 2478   # WhisperMessageEvent

    # User Data
    USER_OBJECT                      = 1327   # UserObjectEvent
    NOOBNESS_LEVEL                   = 3583   # NoobnessLevelMessageEvent
    RESPECT_NOTIFICATION             = 474    # RespectNotificationMessageEvent

    # Social
    FRIEND_LIST_UPDATE               = 2656   # FriendListUpdateEvent
    NEW_FRIEND_REQUEST               = 2200   # NewFriendRequestEvent

    # Economy
    ACTIVITY_POINTS                  = 2919   # ActivityPointsMessageEvent
    CREDIT_BALANCE                   = 2994   # CreditBalanceEvent


# =============================================================================
# SULEK.DEV AUTO-FETCH
# Llama a fetch_and_apply_latest_headers() al arrancar para mantener los IDs
# siempre sincronizados con la última versión del cliente Flash de Habbo.
# =============================================================================

# Mapeo: nombre del compositor (API) → atributo de Outgoing / Incoming
_OUTGOING_MAP = {
    'ClientHelloMessageComposer':           'CLIENT_HELLO',
    'InitDiffieHandshakeMessageComposer':   'INIT_DIFFIE_HANDSHAKE',
    'CompleteDiffieHandshakeMessageComposer': 'COMPLETE_DIFFIE_HANDSHAKE',
    'VersionCheckMessageComposer':          'VERSION_CHECK',
    'UniqueIDMessageComposer':              'UNIQUE_ID',
    'SSOTicketMessageComposer':             'SSO_TICKET',
    'InfoRetrieveMessageComposer':          'INFO_RETRIEVE',
    'DisconnectMessageComposer':            'DISCONNECT',
    'LatencyPingRequestMessageComposer':    'LATENCY_PING_REQUEST',
    'PongMessageComposer':                  'PONG',
    'OpenFlatConnectionMessageComposer':    'OPEN_FLAT_CONNECTION',
    'GetGuestRoomMessageComposer':          'GET_GUEST_ROOM',
    'GetInterstitialMessageComposer':       'GET_INTERSTITIAL',
    'QuitMessageComposer':                  'QUIT_ROOM',
    'SelectInitialRoomComposer':            'SELECT_INITIAL_ROOM',
    'UpdateHomeRoomMessageComposer':        'UPDATE_HOME_ROOM',
    'NewNavigatorInitComposer':             'NEW_NAVIGATOR_INIT',
    'NewNavigatorSearchComposer':           'NEW_NAVIGATOR_SEARCH',
    'MoveAvatarMessageComposer':            'MOVE_AVATAR',
    'LookToMessageComposer':                'LOOK_TO',
    'ChangePostureMessageComposer':         'CHANGE_POSTURE',
    'ShoutMessageComposer':                 'SHOUT',
    'ChatMessageComposer':                  'CHAT',
    'WhisperMessageComposer':               'WHISPER',
    'DanceMessageComposer':                 'DANCE',
    'SignMessageComposer':                  'SIGN',
    'AvatarExpressionMessageComposer':      'AVATAR_EXPRESSION',
    'RespectUserMessageComposer':           'RESPECT_USER',
    'ReplenishRespectMessageComposer':      'REPLENISH_RESPECT',
    'ChangeMottoMessageComposer':           'CHANGE_MOTTO',
    'UpdateFigureDataMessageComposer':      'UPDATE_FIGURE',
    'ChangeUserNameMessageComposer':        'CHANGE_USERNAME',
    'ChangeUserNameInRoomMessageComposer':  'CHANGE_USERNAME_IN_ROOM',
    'RequestFriendMessageComposer':         'REQUEST_FRIEND',
    'AvatarEffectActivatedComposer':        'AVATAR_EFFECT_ACTIVATED',
    'AvatarEffectSelectedComposer':         'AVATAR_EFFECT_SELECTED',
    'PurchaseFromCatalogComposer':          'PURCHASE_FROM_CATALOG',
    'IncomeRewardStatusMessageComposer':    'INCOME_REWARD_STATUS',
    'IncomeRewardClaimMessageComposer':     'INCOME_REWARD_CLAIM',
}

_INCOMING_MAP = {
    'InitDiffieHandshakeEvent':             'SERVER_INIT_DIFFIE_HANDSHAKE',
    'CompleteDiffieHandshakeEvent':         'SERVER_COMPLETE_DIFFIE_HANDSHAKE',
    'AuthenticationOKMessageEvent':         'AUTHENTICATION_OK',
    'UniqueMachineIDEvent':                 'REQUEST_MACHINE_ID',
    'GenericErrorEvent':                    'GENERIC_ERROR',
    'UserRightsMessageEvent':               'USER_RIGHTS',
    'IsFirstLoginOfDayEvent':               'IS_FIRST_LOGIN_OF_DAY',
    'DisconnectReasonEvent':                'DISCONNECT_REASON',
    'PingMessageEvent':                     'PING',
    'LatencyPingResponseMessageEvent':      'LATENCY_PING_RESPONSE',
    'FloodControlMessageEvent':             'FLOOD_CONTROL',
    'RemainingMutePeriodEvent':             'REMAINING_MUTE_PERIOD',
    'OpenConnectionMessageEvent':           'OPEN_CONNECTION',
    'RoomReadyMessageEvent':                'ROOM_READY',
    'RoomForwardMessageEvent':              'ROOM_FORWARD',
    'FlatAccessDeniedMessageEvent':         'FLAT_ACCESS_DENIED',
    'DoorbellMessageEvent':                 'DOORBELL',
    'FlatCreatedEvent':                     'FLAT_CREATED',
    'NavigatorSearchResultBlocksEvent':     'NAVIGATOR_SEARCH_RESULT_BLOCKS',
    'FloorHeightMapMessageEvent':           'FLOOR_HEIGHT_MAP',
    'HeightMapMessageEvent':                'HEIGHT_MAP',
    'RoomEntryTileMessageEvent':            'ROOM_ENTRY_TILE',
    'UsersMessageEvent':                    'USERS',
    'UserRemoveMessageEvent':               'USER_REMOVE',
    'UserUpdateMessageEvent':               'USER_UPDATE',
    'UserChangeMessageEvent':               'USER_CHANGE',
    'UserTypingMessageEvent':               'USER_TYPING',
    'ChatMessageEvent':                     'CHAT',
    'ShoutMessageEvent':                    'SHOUT',
    'WhisperMessageEvent':                  'WHISPER',
    'UserObjectEvent':                      'USER_OBJECT',
    'NoobnessLevelMessageEvent':            'NOOBNESS_LEVEL',
    'RespectNotificationMessageEvent':      'RESPECT_NOTIFICATION',
    'FriendListUpdateEvent':                'FRIEND_LIST_UPDATE',
    'NewFriendRequestEvent':                'NEW_FRIEND_REQUEST',
    'ActivityPointsMessageEvent':           'ACTIVITY_POINTS',
    'CreditBalanceEvent':                   'CREDIT_BALANCE',
}


def fetch_and_apply_latest_headers(verbose: bool = True) -> dict:
    """
    Descarga los mensajes de la última versión Flash desde api.sulek.dev
    a un archivo local (sulek_messages.json) y aplica los IDs a
    Outgoing/Incoming + RELEASE_VERSION/CLIENT_TYPE.

    El archivo se guarda junto a constants.py para reutilizarlo si la
    versión no ha cambiado, evitando descargas innecesarias.

    Retorna un dict:
        {
            'version':     str,
            'protocol':    str,
            'updated_out': int,
            'updated_in':  int,
            'cached':      bool,   # True si se usó el archivo ya descargado
            'error':       str | None,
        }
    """
    import requests as _req, json as _json, os as _os

    BASE      = 'https://api.sulek.dev'
    HERE      = _os.path.dirname(_os.path.abspath(__file__))
    CACHE_DIR = _os.path.join(HERE, 'sulek_cache')
    _os.makedirs(CACHE_DIR, exist_ok=True)

    result = {'version': None, 'protocol': None,
              'updated_out': 0, 'updated_in': 0,
              'cached': False, 'error': None}

    try:
        # ── 1. Versión más reciente ───────────────────────────────────
        r = _req.get(f'{BASE}/releases?variant=flash-windows', timeout=8)
        r.raise_for_status()
        releases = r.json()
        if not releases:
            result['error'] = 'No releases found'; return result

        version  = releases[0]['version']
        result['version'] = version

        # ── 2. Protocolo (FLASH28, etc.) ──────────────────────────────
        r2 = _req.get(f'{BASE}/releases/flash-windows/{version}', timeout=8)
        r2.raise_for_status()
        protocol = r2.json().get('protocol', 'UNKNOWN')
        result['protocol'] = protocol

        # ── 3. Descargar mensajes a disco (stream) ────────────────────
        cache_file = _os.path.join(CACHE_DIR, f'{version}_messages.json')

        if _os.path.exists(cache_file):
            # Ya lo tenemos descargado para esta versión
            result['cached'] = True
            if verbose:
                print(f'[SULEK] 📁 Usando caché: {cache_file}')
        else:
            # Descarga completa en streaming → archivo local
            url = f'{BASE}/releases/flash-windows/{version}/messages'
            if verbose:
                print(f'[SULEK] ⬇  Descargando {url} → {cache_file}')
            r3 = _req.get(url, stream=True, timeout=30)
            r3.raise_for_status()
            with open(cache_file, 'wb') as fout:
                for chunk in r3.iter_content(chunk_size=65536):
                    if chunk:
                        fout.write(chunk)
            if verbose:
                size_kb = _os.path.getsize(cache_file) // 1024
                print(f'[SULEK] ✅ Descargado ({size_kb} KB)')

        # ── 4. Parsear el JSON local ──────────────────────────────────
        with open(cache_file, 'r', encoding='utf-8') as fin:
            data = _json.load(fin)

        msgs     = data.get('messages', {})
        out_list = msgs.get('outgoing', [])
        in_list  = msgs.get('incoming', [])

        out_lookup = {p['name']: p['id'] for p in out_list}
        in_lookup  = {p['name']: p['id'] for p in in_list}

        # ── 5. Aplicar a las clases Outgoing / Incoming ───────────────
        for composer_name, attr in _OUTGOING_MAP.items():
            if composer_name in out_lookup:
                setattr(Outgoing, attr, out_lookup[composer_name])
                result['updated_out'] += 1

        for event_name, attr in _INCOMING_MAP.items():
            if event_name in in_lookup:
                setattr(Incoming, attr, in_lookup[event_name])
                result['updated_in'] += 1

        # ── 6. Actualizar globals de versión ──────────────────────────
        global RELEASE_VERSION, CLIENT_TYPE
        RELEASE_VERSION = version
        CLIENT_TYPE     = protocol

        if verbose:
            src = '(caché)' if result['cached'] else '(descarga nueva)'
            print(f'[SULEK] 🎯 {version} | {protocol} {src} | '
                  f'OUT:{result["updated_out"]} IN:{result["updated_in"]} actualizados')

    except Exception as e:
        result['error'] = str(e)
        if verbose:
            print(f'[SULEK] ⚠️  Error: {e} — usando valores integrados de fallback')

    return result
