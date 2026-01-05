import bpy
import sounddevice as sd
import time
import json
import os
import numpy as np
import queue
import threading
from janome.tokenizer import Tokenizer

from .language_config import (
    DISPLAY_TO_CODE,
    CODE_TO_DISPLAY,
    ENABLED_LANGUAGES,
    DEFAULT_LANGUAGE,
    WHISPER_CODE_MAP,
    LANGUAGE_KEYS
)

# 音声認識ライブラリのインポート（faster-whisper優先）
try:
    from faster_whisper import WhisperModel
    # CPU環境での最適化設定
    model = WhisperModel(
        "small",
        device="cpu",
        compute_type="float32",  # メモリ使用量を削減
        cpu_threads=4,        # CPUスレッド数を制限
        num_workers=1         # ワーカー数を制限してメモリ節約
    )

    WHISPER_TYPE = "faster-whisper"
    print("音声認識: faster-whisper を使用（最適化設定）")
except ImportError:
    try:
        import whisper
        model = whisper.load_model("base")  # 従来のWhisperモデル読み込み
        WHISPER_TYPE = "whisper"
        print("音声認識: whisper を使用")
    except ImportError:
        model = None
        WHISPER_TYPE = None
        print("⚠️ 音声認識ライブラリが見つかりません")

try:
    import pywhispercpp
    print("pywhispercpp は Blender で使用可能です")
except ImportError:
    print("pywhispercpp は Blender で使用できません")


q = queue.Queue()

######################################
#  言語変換関数群（高速版）
######################################
def display_name_to_code(display_name):
    """表示名から言語コードに変換（高速版）"""
    return DISPLAY_TO_CODE.get(display_name, display_name.lower())

def code_to_display_name(code):
    """言語コードから表示名に変換（高速版）"""
    return CODE_TO_DISPLAY.get(code, code)

def get_enabled_languages():
    """有効な言語のリストを取得（高速版）"""
    return ENABLED_LANGUAGES  # 事前計算済みリストを返すだけ

def get_default_language():
    """デフォルト言語コードを取得（高速版）"""
    return DEFAULT_LANGUAGE

######################################
#  認識可能の言語取得
######################################
def get_active_language():
    """チェックボックスで選択されている言語取得（高速版）"""
    try:
        if hasattr(bpy.context.scene, 'bvc_language_props'):
            props = bpy.context.scene.bvc_language_props            
            
            for key, name in props.language_keys:
                if hasattr(props, key) and getattr(props, key):
                    # 事前計算済み辞書使用（超高速）
                    """
                    dict.get(key, default_value)
                    key: 検索するキー
                    default_value: キーが見つからない場合に返すデフォルト値
                    """
                    language_code = DISPLAY_TO_CODE.get(name, name.lower())
                    #print(f"🌐 選択言語: {name} → {language_code}")
                    return language_code
        
        print(f"⚠️ デフォルト言語 '{DEFAULT_LANGUAGE}' を使用")
        return DEFAULT_LANGUAGE
        
    except Exception as e:
        print(f"❌ 言語取得エラー: {e}")
        return DEFAULT_LANGUAGE

def get_whisper_language_setting():
    """音声認識用の言語設定を取得（高速版）"""
    try:
        active_language = get_active_language()
        
        if active_language:
            # 事前計算済み辞書使用（超高速）
            whisper_code = WHISPER_CODE_MAP.get(active_language, active_language)
            print(f"🎤 Whisper用言語設定: {whisper_code}")
            return whisper_code
        else:
            return None
            
    except Exception as e:
        print(f"❌ Whisper言語設定エラー: {e}")
        return None
    
###########################################
#   　 　　マルチスレッド音声認識管理
###########################################
class VoiceRecognitionManager:
    """音声認識の全体管理（シングルトン）"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, 'initialized'):
            return
        self.initialized = True
        
        self.audio_processor = None
        self.result_queue = queue.Queue()
        self.is_active = False
        self.current_device = None
        self.last_result = None  # 最後の認識結果を保存
        self.start_time = None   # 開始時刻
        self.status_message = "待機中"  # 状態メッセージ
    
    def start_recognition(self, device_id=None):
        """音声認識を開始"""
        if self.is_active:
            print("音声認識は既にアクティブです")
            return True
            
        if model is None:
            print("⚠️ 音声認識モデルが利用できません")
            self.status_message = "モデル利用不可"
            return False
        
        # デバイス選択
        if device_id is None:
            #ここで渡したIDに対応するデバイスを選択する
            device_id = check_audio_devices()
        
        if device_id is None:
            print("❌ 利用可能な音声デバイスがありません")
            self.status_message = "デバイスなし"
            return False
        
        # オーディオプロセッサを開始
        try:
            self.audio_processor = AudioProcessor(self.result_queue, device_id)
            self.audio_processor.start()
            self.is_active = True
            self.current_device = device_id
            self.start_time = time.time()
            self.status_message = "録音中"
            
            print(f"🎤 音声認識開始 (デバイス: {device_id})")
            return True
        except Exception as e:
            print(f"❌ 音声認識開始エラー: {e}")
            self.status_message = f"開始エラー: {str(e)}"
            return False
    
    def stop_recognition(self):
        """音声認識を停止"""
        if not self.is_active:
            return
        
        self.is_active = False
        self.status_message = "停止中"
        
        if self.audio_processor:
            self.audio_processor.stop()
            self.audio_processor.join(timeout=2.0)
            self.audio_processor = None
        
        # キューをクリア
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break
        
        self.status_message = "待機中"
        print("🛑 音声認識停止")
    
    def get_latest_result(self):
        """最新の認識結果を取得"""
        try:
            result = self.result_queue.get_nowait()
            self.last_result = result  # 最後の結果を保存
            return result
        except queue.Empty:
            return None
    
    def get_status_info(self):
        """詳細な状態情報を取得"""
        info = {
            "is_active": self.is_active,
            "status_message": self.status_message,
            "current_device": self.current_device,
            "last_result": self.last_result
        }
        
        if self.start_time and self.is_active:
            info["duration"] = int(time.time() - self.start_time)
        
        return info


class AudioProcessor(threading.Thread):
    """バックグラウンドでの音声処理"""
    
    def __init__(self, result_queue, device_id):
        super().__init__(daemon=True)
        self.result_queue = result_queue
        self.device_id = device_id
        self.audio_queue = queue.Queue()
        self.is_running = False
    
    def audio_callback(self, indata, frames, time, status):
        """音声データのコールバック"""
        if status:
            print(f"⚠️ オーディオステータス: {status}")
        if self.is_running:
            if hasattr(bpy.context.scene, 'bvc_device_props'):
                props = bpy.context.scene.bvc_device_props
                volume_threshold = props.volume_threshold
                # 音声データの音量レベルを簡単チェック
                volume_level = np.max(np.abs(indata))
                if volume_level > volume_threshold:  # 有効な音声がある場合
                    print("♪", end="", flush=True)  # 音声検出マーク
                else:
                    print("_", end="", flush=True)   # 無音マーク
                
                self.audio_queue.put(indata.copy())
        
    def run(self):
        """メインの音声処理ループ"""
        self.is_running = True
        
        try:
            # デバイスが有効かどうか事前チェック
            devices = sd.query_devices()
            if self.device_id >= len(devices) or devices[self.device_id]['max_input_channels'] == 0:
                raise Exception(f"デバイス {self.device_id} は無効または入力チャンネルがありません")
            
            with sd.InputStream(
                callback=self.audio_callback,
                channels=1,
                samplerate=16000,
                device=self.device_id,
                blocksize=1024
            ):
                print(f"🎙️ 音声入力開始 (デバイス: {self.device_id} - {devices[self.device_id]['name']})")
                
                while self.is_running:
                    # 音声データを蓄積してから認識
                    audio_chunks = []
                    chunk_count = 0
                    
                    print("🔊 音声収集中...", end="", flush=True)
                    
                    # 約2秒分のデータを蓄積
                    while chunk_count < 32 and self.is_running:  # 32 chunks ≈ 2秒
                        try:
                            chunk = self.audio_queue.get(timeout=0.1)
                            audio_chunks.append(chunk)
                            chunk_count += 1
                            
                            # プログレス表示（8チャンクごと）
                            if chunk_count % 8 == 0:
                                print("●", end="", flush=True)
                                
                        except queue.Empty:
                            print(".", end="", flush=True)  # 待機中を表示
                            continue
                    
                    if audio_chunks and self.is_running:
                        print(" [完了] ", end="", flush=True)
                        self.process_audio_chunks(audio_chunks)
                        
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 音声処理エラー: {error_msg}")
            
            # エラーの種類に応じた対処法を提示
            if "Invalid device" in error_msg or "PaErrorCode -9996" in error_msg:
                print("💡 対処法:")
                print("  1. デバイスが接続されているか確認してください")
                print("  2. デバイスが他のアプリで使用されていないか確認してください")
                print("  3. Windowsの音声設定でデバイスが有効になっているか確認してください")
                print("  4. デバイスドライバーを再インストールしてみてください")
            elif "Permission" in error_msg or "Access" in error_msg:
                print("💡 対処法:")
                print("  1. Windowsプライバシー設定でマイクアクセスを許可してください")
                print("  2. 管理者権限でBlenderを実行してみてください")
            
            self.result_queue.put({"error": error_msg, "suggestions": "デバイス接続とアクセス権限を確認してください"})
        
        print("🛑 音声処理スレッド終了")
    
    def process_audio_chunks(self, audio_chunks):
        """音声チャンクを認識処理"""
        try:
            print("🎤 音声データ処理開始...", end="", flush=True)
            
            # チャンクを結合
            audio = np.concatenate(audio_chunks, axis=0).flatten()
            
            if hasattr(bpy.context.scene, 'bvc_device_props'):
                props = bpy.context.scene.bvc_device_props
                volume_threshold = props.volume_threshold
                # 音声レベルチェック（無音判定）
                if np.max(np.abs(audio)) < volume_threshold:
                    print(" [無音でスキップ]")
                    return  # 無音の場合はスキップ
                
                # faster-whisper または whisper で認識
                if WHISPER_TYPE == "faster-whisper":
                    
                    # 選択された言語設定を取得
                    language_setting = get_whisper_language_setting()
                    print(f"🌐 使用言語: {language_setting}")
                    
                    segments, info = model.transcribe(
                        audio,
                        language=get_active_language(),  # 動的言語設定
                        beam_size=5,
                        best_of=5,
                        temperature=0.0,
                        vad_filter=False,  # VADフィルターを無効化（onnxruntime不要）
                    )
                    text = "".join([segment.text for segment in segments]).strip()
                
                elif WHISPER_TYPE == "whisper":
                    result = model.transcribe(audio, language="ja")
                    text = result["text"].strip()
                else:
                    print(" [認識モデル無効]")
                    return
                
                # 結果をキューに送信
                if text:
                    print(f" ✅ 認識結果: {text}")
                    self.result_queue.put({
                        "text": text,
                        "timestamp": time.time(),
                        "confidence": getattr(info, 'language_probability', 1.0) if WHISPER_TYPE == "faster-whisper" else 1.0
                    })
                else:
                    print(" [認識結果なし]")
            else:
                print(" [プロパティ取得エラー]")
        
        except Exception as e:
            print(f" ❌ 音声認識エラー: {e}")
            print(f"❌ 音声認識エラー: {e}")
    
    def stop(self):
        """スレッドの停止"""
        self.is_running = False

# グローバルインスタンス
# VoiceRecognitionManagerクラスのインスタンスを作成して、モジュール全体で共有できるグローバル変数
voice_manager = VoiceRecognitionManager()

#  現在のモードが指定のモードかチェックする
def check_viewmode(arg_checktype:str) -> bool:
    # 現在のモードをチェックする
    # (https://docs.blender.org/api/current/bpy.context.html#bpy.context.mode)
    modetype = bpy.context.mode
    return (arg_checktype == modetype)

#######################################
#  　 　　音声デバイスのチェックと選択
#######################################
def check_audio_devices():
    """利用可能な音声デバイスをチェックして適切なデバイスを選択"""
    try:
        print("🎙️ 利用可能な音声デバイス:")
        devices = sd.query_devices()
        
        input_devices = []
        mic_devices = []  # マイクデバイス専用リスト
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"  {i}: {device['name']} (入力チャンネル: {device['max_input_channels']})")
                input_devices.append(i)
                
                # マイクっぽいデバイスを優先的に記録
                device_name = device['name'].lower()
                if any(keyword in device_name for keyword in ['mic', 'マイク', 'microphone']):
                    mic_devices.append(i)
        
        if not input_devices:
            print("❌ 音声入力デバイスが見つかりません")
            return None
        
        # ユーザーが選択したデバイスを優先的に使用
        try:
            if hasattr(bpy.context.scene, 'bvc_device_props'):
                props = bpy.context.scene.bvc_device_props
                selected_device_name = props.selected_device
                
                # "未選択"でない場合、選択されたデバイス名に対応するIDを探す
                if selected_device_name != "未選択":
                    print(f"🔍 選択されたデバイスを検索中: {selected_device_name}")
                    
                    for i, device in enumerate(devices):
                        if device['name'] == selected_device_name and i in input_devices:
                            print(f"✅ 選択されたデバイスが見つかりました: {selected_device_name} (ID: {i})")
                            # デバイスをテストしてから返す
                            if test_audio_device(i):
                                return i
                            else:
                                print(f"⚠️ 選択されたデバイス {i} はテストに失敗しました")
                    
                    print(f"⚠️ 選択されたデバイス '{selected_device_name}' が見つからないか利用できないため、自動選択に切り替えます")
        except Exception as e:
            print(f"⚠️ 選択デバイス確認エラー: {e}")
        
        # デフォルトの入力デバイスを試す
        try:
            default_device = sd.query_devices(kind='input')
            default_id = None
            
            # デフォルトデバイスのIDを探す
            for i, device in enumerate(devices):
                if device['name'] == default_device['name']:
                    default_id = i
                    break
            
            if default_id is not None and default_id in input_devices:
                print(f"✅ デフォルト入力デバイス: {default_device['name']} (ID: {default_id})")
                # デフォルトデバイスもテストしてから返す
                if test_audio_device(default_id):
                    return default_id
                else:
                    print(f"⚠️ デフォルトデバイス {default_id} はテストに失敗しました")
        except Exception as e:
            print(f"⚠️ デフォルトデバイス確認エラー: {e}")
        
        # マイクデバイスがあれば優先的に使用
        if mic_devices:
            for selected_device in mic_devices:
                print(f"🧪 マイクデバイスをテスト中: デバイス {selected_device}")
                if test_audio_device(selected_device):
                    print(f"🎤 マイクデバイスを選択: デバイス {selected_device}")
                    return selected_device
                else:
                    print(f"⚠️ マイクデバイス {selected_device} はテストに失敗しました")
        
        # その他の入力デバイスから選択（ステレオミキサーを避ける）
        for device_id in input_devices:
            device_name = devices[device_id]['name'].lower()
            if 'stereo' not in device_name and 'ステレオ' not in device_name and 'mix' not in device_name:
                print(f"🧪 入力デバイスをテスト中: デバイス {device_id}")
                if test_audio_device(device_id):
                    print(f"🔊 入力デバイスを選択: デバイス {device_id}")
                    return device_id
                else:
                    print(f"⚠️ 入力デバイス {device_id} はテストに失敗しました")
        
        # 最後の手段として最初のデバイスを試す（テスト無し）
        if input_devices:
            selected_device = input_devices[0]
            print(f"⚠️ フォールバック: デバイス {selected_device} を使用します（テスト無し）")
            return selected_device
            
    except Exception as e:
        print(f"❌ デバイスチェックエラー: {e}")
        return None
    
########################################
#  　 　　デバイスのテスト録音
########################################
def test_audio_device(device_id):
    """選択されたデバイスでテスト録音を実行"""
    try:
        print(f"🧪 デバイス {device_id} をテスト中...")
        test_queue = queue.Queue()
        
        def test_callback(indata, frames, time, status):
            test_queue.put(indata.copy())
        
        # 短時間のテスト録音
        with sd.InputStream(
            callback=test_callback,
            channels=1,
            samplerate=16000,
            device=device_id,
            blocksize=1024
        ):
            sd.sleep(500)  # 0.5秒待機
        
        # テストデータがあるかチェック
        if not test_queue.empty():
            print("✅ デバイステスト成功")
            return True
        else:
            print("⚠️ デバイステスト: データが取得できませんでした")
            return False
            
    except Exception as e:
        print(f"❌ デバイステストエラー: {e}")
        return False


def callback(indata, frames, time, status):
    if status:
        print("Status:", status)
    print("📦 音声データ:", indata.shape)
    q.put(indata.copy())

def recognize_from_queue():
    """音声認識を実行する関数（faster-whisper と whisper の両方に対応）"""
    audio_chunks = []
    while not q.empty():
        audio_chunks.append(q.get())
    
    if not audio_chunks:
        print("音声データがありません")
        return None
        
    if model is None:
        print("⚠️ 音声認識モデルが利用できません")
        return "音声認識テスト"
    
    try:
        # 複数の録音チャンクを1つの配列に結合し1次元化
        audio = np.concatenate(audio_chunks, axis=0).flatten()
        
        if WHISPER_TYPE == "faster-whisper":
            # faster-whisperを使用（高速処理設定）
            language_setting = get_whisper_language_setting()
            segments, info = model.transcribe(
                audio, 
                #language=language_setting,  # 動的言語設定
                language=get_active_language(),  # 動的言語設定,  # 動的言語設定
                beam_size=1,        # ビーム幅を小さくして高速化
                best_of=1,          # 候補数を制限
                temperature=0,      # 確定的な結果を得る
                vad_filter=False,   # VADフィルターを無効化（onnxruntime不要）
            )
            # セグメントを結合してテキストを取得
            text_segments = []
            for segment in segments:
                text_segments.append(segment.text)
            result_text = "".join(text_segments).strip()
            print("認識結果 (faster-whisper):", result_text)
            return result_text
            
        elif WHISPER_TYPE == "whisper":
            # 従来のwhisperを使用
            result = model.transcribe(audio, language="ja")
            print("認識結果 (whisper):", result["text"])
            return result["text"]
            
    except Exception as e:
        print(f"音声認識エラー: {e}")
        return None
    
    return None



######################################
#  　 　　マイクデバイスの取得
######################################
def get_unique_mics():
    devices = sd.query_devices()
    seen = set()
    mic_list = []
    result_mics = []
    for device in devices:
        if device['max_input_channels'] > 0:
            name = device['name']
            name_lower = name.lower()
            exclude_keywords = ['stereo', 'wave', 'mapper', 'line', 'asio']
            if ('mic' in name_lower or 'マイク' in name) and not any(
                kw in name_lower for kw in exclude_keywords
            ):
                if name not in seen:
                    seen.add(name)
                    mic_list.append(device)

    for i, device in enumerate(mic_list):
        result_mics.append({'Index': device['index'], 'Name': device['name']})
    return result_mics #{'Index': device['index'], 'Name': device['name']}
######################################
#  　 　　デバイスのリストの初期化
######################################
def init_device_list():
    props = bpy.context.scene.bvc_device_props
    props.device_list.clear()
     # デバイス認識待ち（必要なら調整）
    unique_mics = get_unique_mics()
    for mic in unique_mics:
        item = props.device_list.add()
        item.device_name = mic['Name']
        #print("追加:", item.device_name)

    addon_dir = os.path.dirname(__file__)
    json_path = os.path.join(addon_dir, "devices.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(unique_mics, f, ensure_ascii=False, indent=2)
    
    for item in props.device_list:
        print(item.device_name)

######################################
#  　 　　言語選択関連の関数
######################################
def get_selected_languages_array():
    """選択された言語のBoolPropertyを配列形式で取得"""
    try:
        if not hasattr(bpy.context.scene, 'bvc_language_props'):
            print("bvc_language_props が見つかりません")
            return []
        
        props = bpy.context.scene.bvc_language_props
        selected_languages = []
        
        # language_keysからBoolPropertyの状態をチェック
        for key, name in props.language_keys:
            if hasattr(props, key):
                is_selected = getattr(props, key)
                selected_languages.append({
                    'code': key.lower(),  # "JA" -> "ja"
                    'name': name,         # "日本語"
                    'selected': is_selected
                })
        
        return selected_languages
        
    except Exception as e:
        print(f"❌ 言語選択状態取得エラー: {e}")
        return []

def get_active_language_codes():
    """アクティブ（選択中）な言語コードのリストを取得"""
    try:
        selected_languages = get_selected_languages_array()
        active_codes = []
        
        for lang in selected_languages:
            if lang['selected']:
                active_codes.append(lang['code'])
        
        # デフォルトで日本語を返す（何も選択されていない場合）
        if not active_codes:
            active_codes = ['ja']
        
        return active_codes
        
    except Exception as e:
        print(f"❌ アクティブ言語コード取得エラー: {e}")
        return ['ja']

def get_whisper_language_setting():
    """音声認識用の言語設定を取得"""
    try:
        active_codes = get_active_language_codes()
        
        # 単一言語の場合
        if len(active_codes) == 1:
            return active_codes[0]
        
        # 複数言語の場合は自動検出を使用（Whisperは単一言語のみサポート）
        elif len(active_codes) > 1:
            print(f"⚠️ 複数言語選択中 {active_codes} - 自動検出を使用")
            return None  # 自動検出
        
        # 何も選択されていない場合
        else:
            return None  # 自動検出
            
    except Exception as e:
        print(f"❌ Whisper言語設定取得エラー: {e}")
        return None  # 自動検出

######################################
#  　 　　jsonファイルの読み込み
######################################
# JSONファイルを読み込む
def read_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"ファイルが見つかりません: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSONの解析エラー: {e}")
        return None

######################################
#  　 　　jsonコマンドデータの読み込み
######################################
def load_commands_from_json():
    """JSONファイルから音声コマンドを読み込んでPropertyに設定"""
    
    # アドオンディレクトリのcommand.jsonを読み込み
    addon_dir = os.path.dirname(__file__)
    json_path = os.path.join(addon_dir, "command.json")
    
    try:
        data = read_json_file(json_path)
        if not data:
            print("JSONデータの読み込みに失敗しました")
            return False
        
        # bpy.contextが利用可能かチェック
        try:
            scene = bpy.context.scene
        except (AttributeError, RuntimeError):
            print("コンテキストが利用できません - 後で再実行してください")
            return False
        
        # コマンドプロパティが存在するかチェック
        if not hasattr(scene, 'bvc_command_props'):
            print("bvc_command_props が登録されていません")
            return False
            
        command_props = scene.bvc_command_props
        
        # CollectionPropertyが初期化されているかチェック
        try:
            # まず既存のデータをクリア
            if hasattr(command_props, 'language_commands'):
                # _PropertyDeferredかどうかをチェック
                prop_type = str(type(command_props.language_commands))
                if '_PropertyDeferred' in prop_type:
                    print("CollectionPropertyがまだ初期化されていません")
                    return False
                
                # 安全にクリア
                while len(command_props.language_commands) > 0:
                    command_props.language_commands.remove(0)
                    
            else:
                print("language_commandsプロパティが見つかりません")
                return False
                
        except (AttributeError, TypeError, IndexError) as e:
            print(f"CollectionPropertyアクセスエラー: {e}")
            return False
        
        # JSONデータから言語別コマンドを設定
        for lang_name, commands in data.items():
            try:
                # 新しい言語コマンドアイテムを追加
                lang_item = command_props.language_commands.add()
                lang_item.language_name = lang_name

                # コマンドを追加
                for cmd_key, cmd_val in commands.items():
                    cmd_item = lang_item.commands.add()
                    cmd_item.command_key = str(cmd_key)
                    # 新形式: description/code両方を持つ場合
                    if isinstance(cmd_val, dict):
                        cmd_item.command_description = str(cmd_val.get("description", ""))
                        # code属性が存在する場合のみセット
                        if hasattr(cmd_item, "command_code"):
                            cmd_item.command_code = str(cmd_val.get("code", ""))
                    else:
                        # 旧形式: 文字列のみ
                        cmd_item.command_description = str(cmd_val)
                        if hasattr(cmd_item, "command_code"):
                            cmd_item.command_code = ""
            except Exception as e:
                print(f"言語 '{lang_name}' の追加中にエラー: {e}")
                continue
                
        print(f"JSONから{len(command_props.language_commands)}言語のコマンドを読み込みました")
        return True
        
    except Exception as e:
        print(f"JSONコマンド読み込みエラー: {e}")
        return False


######################################
#  　 　　command_itemsからbvc_command_propsへの同期
######################################
def sync_command_items_to_bvc_props():
    """command_itemsの変更をbvc_command_propsに同期"""
    
    try:
        scene = bpy.context.scene
        
        if not (hasattr(scene, 'command_items') and hasattr(scene, 'bvc_command_props')):
            print("必要なプロパティが見つかりません")
            return False
        
        command_props = scene.bvc_command_props
        current_language = command_props.current_language
        
        if not current_language:
            print("現在の言語が設定されていません")
            return False
        
        # 現在の言語に対応するlanguage_commandsを見つけて更新
        for lang_item in command_props.language_commands:
            if lang_item.language_name == current_language:
                # 既存のコマンドをクリア
                lang_item.commands.clear()
                
                # command_itemsからコマンドを再構築
                for item in scene.command_items:
                    new_cmd = lang_item.commands.add()
                    new_cmd.command_key = item.name
                    new_cmd.command_description = item.description
                    new_cmd.command_code = item.code
                
                print(f"【{current_language}】に {len(scene.command_items)} 個のコマンドを同期しました")
                return True
        
        print(f"言語 '{current_language}' が見つかりませんでした")
        return False
        
    except Exception as e:
        print(f"同期エラー: {e}")
        return False

######################################
#  　 　　Propertyからjsonファイルに音声コマンドを保存
######################################
def save_commands_to_json():
    """PropertyからJSONファイルに音声コマンドを保存"""
    
    try:
        scene = bpy.context.scene
        
        if not hasattr(scene, 'bvc_command_props'):
            print("bvc_command_props が見つかりません")
            print("error1")
            return False
            
        command_props = scene.bvc_command_props
        
        # CollectionPropertyが初期化されているかチェック
        if not hasattr(command_props, 'language_commands'):
            print("language_commandsプロパティが見つかりません")
            print("error2")
            return False
        
        # PropertyからJSONデータを構築
        json_data = {}
        try:
            for lang_items in command_props.language_commands:
                print(f"lang_item : {lang_items}")
                lang_data = {}
                for cmd_item in lang_items.commands:
                    print(f"cmd_item : {cmd_item}")
                    lang_data[cmd_item.command_key] = {
                        "description": cmd_item.command_description,
                        "code": cmd_item.command_code
                        #"code": getattr(cmd_item, "code", "")
                    }
                json_data[lang_items.language_name] = lang_data
                
        except Exception as e:
            print(f"データ構築エラー: {e}")
            print("error3")
            return False
        
        # アドオンディレクトリに保存
        addon_dir = os.path.dirname(__file__)
        json_path = os.path.join(addon_dir, "command.json")
        
        with open(json_path, 'w', encoding='utf-8') as file:
            json.dump(json_data, file, ensure_ascii=False, indent=2)
            
        print(f"JSONに{len(json_data)}言語のコマンドを保存しました")
        return True
        
    except Exception as e:
        print(f"JSONコマンド保存エラー: {e}")
        print("error4")
        return False
    

######################################
#  　 　　pywhispercppストリーミング実装
######################################

import pywhispercpp as pwcpp

class PyWhisperCppStreamingManager:
    """pywhispercppを使用したストリーミング音声認識管理"""
    
    def __init__(self):
        self.model = None
        self.streaming = None
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.stream_thread = None
        self.audio_thread = None
        
        # ストリーミング設定
        self.sample_rate = 16000  # Whisperの標準サンプルレート
        self.chunk_size = 1024    # チャンクサイズ
        self.channels = 1         # モノラル
        
    def initialize_model(self, model_path="models/ggml-base.bin"):
        """モデルの初期化"""
        try:
            # pywhispercppモデルの作成
            params = pwcpp.Params()
            params.model = model_path
            params.language = get_active_language()  # 自動言語検出
            params.n_threads = 4      # スレッド数
            
            self.model = pwcpp.Model(params)
            
            # ストリーミングオブジェクトの作成
            self.streaming = pwcpp.StreamingWhisper(self.model)
            
            print(f"✅ pywhispercpp モデル初期化成功: {model_path}")
            return True
            
        except Exception as e:
            print(f"❌ pywhispercpp モデル初期化失敗: {e}")
            return False
    
    def audio_callback(self, indata, frames, time, status):
        """音声入力コールバック"""
        if status:
            print(f"⚠️ 音声入力エラー: {status}")
        
        # float32をint16に変換（pywhispercppが期待する形式）
        audio_data = (indata.flatten() * 32767).astype(np.int16)
        
        # キューに音声データを追加
        if not self.audio_queue.full():
            self.audio_queue.put(audio_data)
    
    def streaming_worker(self):
        """ストリーミング処理ワーカー"""
        print("🎤 ストリーミング処理開始")
        
        while self.is_running:
            try:
                # 音声データを取得（タイムアウト付き）
                audio_chunk = self.audio_queue.get(timeout=1.0)
                
                # ストリーミング認識実行
                if self.streaming:
                    result = self.streaming.process_audio(audio_chunk)
                    
                    if result and result.strip():
                        # 結果をキューに追加
                        self.result_queue.put({
                            "text": result,
                            "timestamp": time.time(),
                            "is_final": True  # pywhispercppでは基本的に最終結果
                        })
                        print(f"\n🎯 認識結果: {result}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ ストリーミング処理エラー: {e}")
                break
        
        print("🛑 ストリーミング処理終了")
    
    def start_streaming(self, device_id=None):
        """ストリーミング開始"""
        if self.is_running:
            print("⚠️ ストリーミングは既に実行中です")
            return False
        
        if not self.model or not self.streaming:
            print("❌ モデルが初期化されていません")
            return False
        
        try:
            # 音声入力ストリームを開始
            self.stream = sd.InputStream(
                device=device_id,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                callback=self.audio_callback,
                dtype=np.float32
            )
            
            self.stream.start()
            self.is_running = True
            
            # ストリーミング処理スレッドを開始
            self.stream_thread = threading.Thread(target=self.streaming_worker)
            self.stream_thread.daemon = True
            self.stream_thread.start()
            
            print("✅ pywhispercpp ストリーミング開始")
            return True
            
        except Exception as e:
            print(f"❌ ストリーミング開始エラー: {e}")
            return False
    
    def stop_streaming(self):
        """ストリーミング停止"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 音声ストリーム停止
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        
        # スレッド終了待機
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=2.0)
        
        # キューをクリア
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        print("🛑 pywhispercpp ストリーミング停止")
    
    def get_latest_result(self):
        """最新の認識結果を取得"""
        results = []
        while not self.result_queue.empty():
            try:
                result = self.result_queue.get_nowait()
                results.append(result)
            except queue.Empty:
                break
        return results



######################################
#  　 　　改良版ストリーミング（VAD付き）
######################################
class AdvancedPyWhisperCppStreaming(PyWhisperCppStreamingManager):
    """VAD（Voice Activity Detection）付きストリーミング"""
    
    def __init__(self):
        super().__init__()
        self.audio_buffer = []
        self.buffer_size = 16000 * 3  # 3秒分のバッファ
        self.silence_threshold = 0.01
        self.min_speech_duration = 0.5  # 最小音声長（秒）
        
    def is_speech(self, audio_chunk):
        """音声かどうかを判定（簡単なVAD）"""
        volume = np.sqrt(np.mean(audio_chunk**2))
        return volume > self.silence_threshold
    
    def streaming_worker_with_vad(self):
        """VAD付きストリーミング処理"""
        print("🎤 VAD付きストリーミング処理開始")
        
        while self.is_running:
            try:
                audio_chunk = self.audio_queue.get(timeout=1.0)
                
                # VADチェック
                if self.is_speech(audio_chunk):
                    # 音声を検出した場合、バッファに追加
                    self.audio_buffer.extend(audio_chunk)
                    
                    # バッファサイズを制限
                    if len(self.audio_buffer) > self.buffer_size:
                        self.audio_buffer = self.audio_buffer[-self.buffer_size:]
                
                else:
                    # 無音の場合、バッファに音声があれば処理
                    if len(self.audio_buffer) > self.sample_rate * self.min_speech_duration:
                        # 音声認識実行
                        audio_array = np.array(self.audio_buffer, dtype=np.int16)
                        
                        if self.streaming:
                            result = self.streaming.process_audio(audio_array)
                            
                            if result and result.strip():
                                self.result_queue.put({
                                    "text": result,
                                    "timestamp": time.time(),
                                    "is_final": True,
                                    "duration": len(audio_array) / self.sample_rate
                                })
                                print(f"🎯 VAD認識結果: {result}")
                    
                    # バッファをクリア
                    self.audio_buffer = []
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ VADストリーミング処理エラー: {e}")
                break
        
        print("🛑 VADストリーミング処理終了")
    
    def start_streaming_with_vad(self, device_id=None):
        """VAD付きストリーミング開始"""
        if self.start_streaming(device_id):
            # 通常のワーカーを停止してVADワーカーに置き換え
            if self.stream_thread:
                self.stream_thread.join(timeout=1.0)
            
            self.stream_thread = threading.Thread(target=self.streaming_worker_with_vad)
            self.stream_thread.daemon = True
            self.stream_thread.start()
            
            print("✅ VAD付きストリーミング開始")
            return True
        return False

# グローバルインスタンス
pywhisper_streaming_manager = None

def get_pywhisper_streaming_manager():
    """ストリーミングマネージャーのシングルトン取得"""
    global pywhisper_streaming_manager
    if pywhisper_streaming_manager is None:
        pywhisper_streaming_manager = AdvancedPyWhisperCppStreaming()
        # モデル初期化
        addon_dir = os.path.dirname(__file__)
        model_path = os.path.join(addon_dir, "models", "ggml-base.bin")
        pywhisper_streaming_manager.initialize_model(model_path)
    
    return pywhisper_streaming_manager

######################################
#  　 　　統合音声認識管理（改良版）
######################################
def start_realtime_recognition(device_id=None):
    """リアルタイム音声認識開始"""
    manager = get_pywhisper_streaming_manager()
    return manager.start_streaming_with_vad(device_id)

def stop_realtime_recognition():
    """リアルタイム音声認識停止"""
    if pywhisper_streaming_manager:
        pywhisper_streaming_manager.stop_streaming()

def get_realtime_results():
    """リアルタイム認識結果取得"""
    if pywhisper_streaming_manager:
        return pywhisper_streaming_manager.get_latest_result()
    return []

######################################
#  　 　　カタカナ変換
######################################
def to_katakana(text):
    t = Tokenizer()
    result = ''
    for token in t.tokenize(text):
        # token.reading が読み（カナ）を返す
        reading = token.reading
        if reading == '*':  # 読み情報がない場合はそのまま
            result += token.surface
        else:
            result += reading
    return result