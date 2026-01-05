"""
言語設定定義ファイル
高速アクセスのためPython辞書として定義
"""

# 言語コード変換マップ
LANGUAGE_MAPPING = {
    "display_name_to_code": {
        "日本語": "ja",
        "English": "en", 
        "中文": "zh",
        "Español": "es",
        "Français": "fr",
        "Deutsch": "de",
        "Italiano": "it",
        "한국어": "ko",
        "Русский": "ru",
        "Português": "pt"
    },
    "code_to_display_name": {
        "ja": "日本語",
        "en": "English",
        "zh": "中文", 
        "es": "Español",
        "fr": "Français",
        "de": "Deutsch",
        "it": "Italiano",
        "ko": "한국어",
        "ru": "Русский",
        "pt": "Português"
    }
}

# サポート言語定義
SUPPORTED_LANGUAGES = [
    {"code": "ja", "display_name": "日本語", "whisper_code": "ja", "enabled": True},
    {"code": "en", "display_name": "English", "whisper_code": "en", "enabled": True}, 
    {"code": "zh", "display_name": "中文", "whisper_code": "zh", "enabled": True},
    {"code": "es", "display_name": "Español", "whisper_code": "es", "enabled": False},
    {"code": "fr", "display_name": "Français", "whisper_code": "fr", "enabled": False},
    {"code": "de", "display_name": "Deutsch", "whisper_code": "de", "enabled": False},
    {"code": "it", "display_name": "Italiano", "whisper_code": "it", "enabled": False},
    {"code": "ko", "display_name": "한국어", "whisper_code": "ko", "enabled": False},
    {"code": "ru", "display_name": "Русский", "whisper_code": "ru", "enabled": False},
    {"code": "pt", "display_name": "Português", "whisper_code": "pt", "enabled": False}
]

# デフォルト設定
DEFAULT_LANGUAGE = "ja"
AUTO_DETECT_ENABLED = True

# 有効言語の事前計算（高速化）
ENABLED_LANGUAGES = [lang for lang in SUPPORTED_LANGUAGES if lang["enabled"]]

# よく使う変換辞書（事前計算）
DISPLAY_TO_CODE = LANGUAGE_MAPPING["display_name_to_code"]
CODE_TO_DISPLAY = LANGUAGE_MAPPING["code_to_display_name"]

# Blender用言語キー（BoolProperty用）
LANGUAGE_KEYS = [(lang["code"].upper(), lang["display_name"]) for lang in ENABLED_LANGUAGES]

# Whisperコード変換辞書（事前計算）
WHISPER_CODE_MAP = {lang["code"]: lang["whisper_code"] for lang in SUPPORTED_LANGUAGES}