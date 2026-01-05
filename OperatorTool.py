import bpy
from bpy.types import Operator
#from .BVCProperties import *
from .util import *

###########################################
#   　 　　Modal音声認識オペレーター（pywhispercpp対応）
###########################################

import bpy
from bpy.types import Operator
from .util import get_pywhisper_streaming_manager


class VOICE_OT_bvc_mode(Operator):
    bl_idname = "voice.bvc_mode"
    bl_label = "音声コマンド"
    bl_description = "pywhispercpp対応ノンブロッキング音声入力"
    bl_options = {'REGISTER','UNDO'}

    def __init__(self):
        self._timer = None
        self.is_voice_active = False
        self.use_pywhisper = True  # pywhispercpp優先使用

    @classmethod
    def poll(cls, context):
        """オペレーターが実行可能かをチェック"""
        return True
    
    def execute(self, context):
        """Modal音声認識の開始/停止（pywhispercpp対応）"""
        # get_voice_manager関数の代わりに直接voice_managerを使用
        try:
            from .util import voice_manager
        except ImportError:
            self.report({'ERROR'}, "音声マネージャーのインポートに失敗しました")
            return {'CANCELLED'}
        
        try:
            import pywhispercpp
            pywhisper_available = True
            print("✅ pywhispercpp が利用可能です")
        except ImportError:
            pywhisper_available = False
            self.use_pywhisper = False
            print("❌ pywhispercpp が利用できません。標準モードで実行します。")
            self.report({'WARNING'}, "pywhispercpp が利用できません。標準モードで実行します。")
        
        # 現在は標準のvoice_managerを使用
        voice_mgr = voice_manager
        
        # 詳細なステータス情報を表示
        status_info = voice_mgr.get_status_info()
        engine_name = "pywhispercpp" if self.use_pywhisper and pywhisper_available else "faster-whisper"
        
        print(f"🔍 使用エンジン: {engine_name}")
        
        if not voice_mgr.is_active:
            # 音声認識開始
            print(f"🎤 {engine_name}で音声認識を開始しようとしています...")
            
            if voice_mgr.start_recognition():
                # タイマーを設定（0.2秒間隔でチェック）
                wm = context.window_manager
                self._timer = wm.event_timer_add(0.2, window=context.window)
                wm.modal_handler_add(self)
                
                self.is_voice_active = True
                self.report({'INFO'}, f"🎤 {engine_name}音声認識開始（ESCで停止）")
                print("✅ Modalモードに入りました")
                return {'RUNNING_MODAL'}
            else:
                error_msg = f"❌ {engine_name}音声認識の開始に失敗しました"
                self.report({'ERROR'}, error_msg)
                return {'CANCELLED'}
        else:
            # 既にアクティブの場合は停止
            print(f"🛑 音声認識を停止します")
            voice_mgr.stop_recognition()
            self.report({'INFO'}, f"🎤 {engine_name}音声認識を停止しました")
            
            # UIの更新を強制
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
            return {'FINISHED'}
    
    def modal(self, context, event):
        """Modalイベント処理（pywhispercpp対応）"""
        from .util import voice_manager
        
        voice_mgr = voice_manager  # 標準のvoice_managerを使用
        
        if event.type == 'TIMER':
            # 定期的な音声結果チェック
            result = voice_mgr.get_latest_result()
            if result:
                engine_name = "pywhispercpp" if self.use_pywhisper else "faster-whisper"
                
                if "error" in result:
                    self.report({'ERROR'}, f"音声認識エラー: {result['error']}")
                    self.cleanup(context)
                    return {'CANCELLED'}
                else:
                    # 音声コマンドを処理
                    self.process_voice_command(result, context)
            
            # UIの更新を強制（パネルの状態表示更新）
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        
        elif event.type == 'ESC':
            # ESCキーで停止
            engine_name = "pywhispercpp" if self.use_pywhisper else "faster-whisper"
            self.report({'INFO'}, f"{engine_name}音声認識を停止しました")
            self.cleanup(context)
            return {'CANCELLED'}
        
        # 他の全てのイベントはBlenderの標準処理に渡す
        return {'PASS_THROUGH'}
    
    def process_voice_command(self, result, context):
        command_props = bpy.context.scene.bvc_command_props
        """認識した音声からコマンドを実行（pywhispercpp対応）"""
        original_text = result.get("text", "").strip()
        # 小文字変換のみ（カタカナ変換は後で言語判定に基づいて行う）
        text = original_text.lower()
        
        if not text:
            return
        
        engine_name = "pywhispercpp" if self.use_pywhisper else "faster-whisper"
        print(f"\n認識音声: '{text}'")
        
        # 信頼度チェック（pywhispercppでは信頼度情報が限定的）
        confidence = result.get("confidence", 1.0)
        if confidence < 0.5:
            print(f"⚠️ 信頼度が低いため処理をスキップ: {confidence:.3f}")
            return
        
        # コマンド実行処理
        executed = False
        try:
            # 1. JSONコマンドと照合（元のテキストと処理済みテキストの両方を渡す）
            executed = self.try_json_commands(text, original_text, context)
            
            # 2. 組み込みコマンド
            if not executed:
                print(f"❓ 未知のコマンド: '{text}'")
            
            # 実行結果の報告
            if executed:
                self.report({'INFO'}, f"✅ [{engine_name}] コマンド実行: {text}")
            else:
                print(f"❓ [{engine_name}] 未知のコマンド: '{text}'")
                
        except Exception as e:
            print(f"❌ [{engine_name}] コマンド処理エラー: {e}")
    
    def try_json_commands(self, text, original_text, context):
        """JSONコマンドの実行を試行"""
        try:
            from .util import load_commands_from_json
            if not load_commands_from_json():
                self.report({'ERROR'}, "JSONファイルの読み込みに失敗しました")
                return {'FINISHED'}

            command_props = bpy.context.scene.bvc_command_props
            
            # 音声認識結果から言語を判定（元のテキストを使用）
            def detect_language_from_text(text):
                """テキストから言語を簡易判定し、JSONの言語名に対応させる"""
                # 日本語文字（ひらがな、カタカナ、漢字）が含まれているかチェック
                hiragana_present = any('\u3040' <= char <= '\u309F' for char in text)
                katakana_present = any('\u30A0' <= char <= '\u30FF' for char in text)
                chinese_chars = any('\u4E00' <= char <= '\u9FAF' for char in text)
                
                # JSONに登録されている実際の言語名を確認
                available_languages = [lang.language_name for lang in command_props.language_commands]
                
                # 日本語判定
                if hiragana_present or katakana_present:
                    # JSONに登録されている日本語の名前を探す
                    for lang_name in available_languages:
                        if '日本' in lang_name or 'japanese' in lang_name.lower() or 'ja' == lang_name.lower():
                            return lang_name
                    return "日本語"  # フォールバック
                
                # 中国語判定
                elif chinese_chars and not hiragana_present and not katakana_present:
                    for lang_name in available_languages:
                        if '中国' in lang_name or 'chinese' in lang_name.lower() or 'zh' == lang_name.lower():
                            return lang_name
                    return "中国語"  # フォールバック
                
                # 英語判定（デフォルト）
                else:
                    # JSONに登録されている英語の名前を探す
                    for lang_name in available_languages:
                        if 'english' in lang_name.lower() or 'en' == lang_name.lower() or '英語' in lang_name:
                            return lang_name
                    # 見つからない場合は最初の言語を使用
                    if available_languages:
                        return available_languages[0]
                    return "英語"  # フォールバック
            
            # 元のテキストから言語を判定
            detected_language = detect_language_from_text(original_text)
            print(f"Detected language from original text '{original_text}': {detected_language}")
            
            # 検出された言語に基づいてテキストを処理
            if detected_language == "日本語":
                # 日本語の場合のみカタカナ変換
                from .util import to_katakana
                processed_text = to_katakana(text)
                print(f"Japanese text converted: '{text}' -> '{processed_text}'")
            else:
                # 他の言語はそのまま
                processed_text = text
            
            # 句読点を削除
            import string
            processed_text = processed_text.translate(str.maketrans('', '', string.punctuation + '。、．，！？'))
            print(f"Punctuation removed: -> '{processed_text}'")
            
            # JSONに登録されている言語リストを表示
            print(f"\n📚 JSONに登録されている言語:")
            for lang_item in command_props.language_commands:
                print(f"  - '{lang_item.language_name}' (コマンド数: {len(lang_item.commands)})")
            print(f"🔍 検出された言語: '{detected_language}'")
            
            #言語別のコマンドリストを確認
            for lang_items in command_props.language_commands:
                # 検出された言語と一致する場合のみチェック
                if lang_items.language_name == detected_language:
                    print(f"Checking commands for language: {lang_items.language_name}")
                    for cmd_item in lang_items.commands:
                        
                        # 日本語の場合のみコマンドキーをカタカナ変換してから比較
                        if detected_language == "日本語":
                            normalized_cmd_key = to_katakana(cmd_item.command_key.lower())
                            print(f"Converted command key: '{cmd_item.command_key.lower()}' -> '{normalized_cmd_key}'")
                        else:
                            normalized_cmd_key = cmd_item.command_key.lower()
                        
                        # コマンドキーからも句読点を削除
                        normalized_cmd_key = normalized_cmd_key.translate(str.maketrans('', '', string.punctuation + '。、．，！？'))
                        print(f"Command key after punctuation removal: '{normalized_cmd_key}'")
                        
                        if normalized_cmd_key in processed_text:
                            print(f"✅ マッチ: '{processed_text}' -> '{cmd_item.command_description}'")
                            # コマンドに対応する処理を実行
                            code = getattr(cmd_item, "command_code", None)
                            print(f"📋 コード取得: {repr(code)}")
                            print(f"📊 コードの状態: 型={type(code).__name__}, 空={code is None or code == ''}, 空白のみ={code.strip() == '' if isinstance(code, str) else 'N/A'}")
                            
                            if code and isinstance(code, str) and code.strip():
                                try:
                                    print(f"🚀 コード実行開始: {cmd_item.command_key}")
                                    # Blenderのグローバル環境を渡す
                                    exec_globals = {
                                        'bpy': bpy,
                                        '__builtins__': __builtins__,
                                    }
                                    # 必要に応じて他のモジュールも追加
                                    exec(code, exec_globals)
                                    print(f"✅ コマンド実行成功: {cmd_item.command_description}")
                                    return True
                                except RuntimeError as e:
                                    # Blender操作エラー（ファイル未保存など）もコマンドとしては認識されている
                                    error_msg = str(e)
                                    print(f"⚠️ コマンド '{cmd_item.command_key}' 実行中にエラー: {error_msg}")
                                    if "Unable to save" in error_msg and "filepath" in error_msg:
                                        print(f"💡 ヒント: ファイルを一度手動で保存してから、このコマンドを使用してください")
                                    return True  # コマンドは認識されたのでTrueを返す
                                except Exception as e:
                                    print(f"❌ コマンド実行エラー: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    return True  # コマンドは認識されたのでTrueを返す
                            else:
                                print(f"⚠️ コードが空またはNullです。コマンドは登録されていますが実行可能なコードがありません")
                                print(f"   コマンド名: {cmd_item.command_key}")
                                print(f"   説明: {cmd_item.command_description}")
                                return False
                        else:
                            print(f"❌ JSON command mismatch: '{processed_text}' does not contain '{normalized_cmd_key}'")
            return False
        except Exception as e:
            print(f"❌ JSON コマンド処理エラー: {e}")
            return False
    
    
    def cleanup(self, context):
        """リソースのクリーンアップ（pywhispercpp対応）"""
        from .util import voice_manager
        
        voice_mgr = voice_manager  # 標準のvoice_managerを使用
        
        # 音声認識停止
        voice_mgr.stop_recognition()
        
        # タイマー削除
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            self._timer = None
        
        self.is_voice_active = False
        
        engine_name = "pywhispercpp" if self.use_pywhisper else "faster-whisper"
        print(f"🧹 {engine_name}リソースクリーンアップ完了")

###########################################
#   　 　　音声デバイスの探索
###########################################
class VOICE_OT_search_device(Operator):

    bl_idname = "voice.search_device"
    bl_label = "音声デバイス"
    bl_description = "仕様可能な音声入力デバイスの更新"
    bl_options = {'REGISTER','UNDO'}

    device_name: bpy.props.StringProperty(name="Device Name",default="未選択", options={"HIDDEN"})  # ←選択したデバイス名を格納するプロパティ

    #selected_deviceを設定する
    def execute(self, context):
        print("device_name:", self.device_name)
        props = context.scene.bvc_device_props
        props.selected_device = self.device_name  # ←選択したデバイス名をセット
        return {'FINISHED'}

###########################################
#   　 　　音声デバイスリストの更新
###########################################
class VOICE_OT_update_device_list(bpy.types.Operator):
    bl_idname = "voice.update_device_list"
    bl_label = "マイクデバイス更新"
    bl_description = "音声デバイスの更新"
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        init_device_list()
        return {'FINISHED'}

#　チェックボックスのクリア
class VOICE_OT_language_clear(Operator):

    bl_idname = "voice.language_clear"
    bl_label = "言語クリア"
    bl_description = "言語設定をクリア"
    bl_options = {'REGISTER','UNDO'}

    def execute(self,context):
        props = bpy.context.scene.bvc_language_props
        for key, label in props.language_keys:
            setattr(props, key, False)
        return {'FINISHED'}

#　チェックボックスの全選択
class VOICE_OT_language_all(Operator):

    bl_idname = "voice.language_all"
    bl_label = "言語をすべて選択"
    bl_description = "言語設定をすべて選択"
    bl_options = {'REGISTER','UNDO'}

    def execute(self,context):
        props = bpy.context.scene.bvc_language_props
        for key, label in props.language_keys:
            setattr(props, key, True)
        return {'FINISHED'}
    

######################################
#  　 　　Commandリストの追加・削除
######################################
#  　 　　Commandリストの追加
class Voice_OT_command_add(bpy.types.Operator):
    bl_idname = "voice.command_add"
    bl_label = "アイテム追加"

    def execute(self, context):
        scene = context.scene
        
        # bvc_command_propsを使用した新しい追加方式
        if hasattr(scene, 'bvc_command_props') and hasattr(scene.bvc_command_props, 'language_commands'):
            command_props = scene.bvc_command_props
            
            # 現在選択されている言語を取得
            current_language = command_props.current_language
            
            if not current_language:
                self.report({'WARNING'}, "言語が選択されていません。先にJSONを読み込んでください。")
                return {'CANCELLED'}
            
            # 該当する言語のコマンドリストに追加
            for lang_item in command_props.language_commands:
                if lang_item.language_name == current_language:
                    new_cmd = lang_item.commands.add()
                    new_cmd.command_key = f"新しいコマンド{len(lang_item.commands)}"
                    new_cmd.command_description = "説明を記入してください"
                    new_cmd.command_code = "print('新しいコマンド実行')"
                    
                    # command_itemsにも同期して追加
                    if hasattr(scene, 'command_items'):
                        item = scene.command_items.add()
                        item.name = new_cmd.command_key
                        item.description = new_cmd.command_description
                        item.code = new_cmd.command_code
                        

                        # valueプロパティが存在する場合のみ設定
                        if hasattr(item, 'value'):
                            item.value = len(scene.command_items)
                        scene.command_index = len(scene.command_items) - 1
                    
                    self.report({'INFO'}, f"新しいコマンドを{current_language}に追加しました")
                    return {'FINISHED'}
            
            self.report({'ERROR'}, f"言語 '{current_language}' が見つかりません")
            return {'CANCELLED'}
        
        else:
            # 従来のcommand_itemsへの追加（フォールバック）
            if not hasattr(scene, 'command_items'):
                self.report({'ERROR'}, "command_items プロパティが初期化されていません")
                return {'CANCELLED'}
                
            item = scene.command_items.add()
            # len()を安全に取得
            item_count = len(scene.command_items)
            item.name = f"Item {item_count}"
            item.description = "処理の説明を記述してください"
            item.code = "コードを記述してください"
            # valueプロパティが存在する場合のみ設定
            if hasattr(item, 'value'):
                item.value = item_count
            scene.command_index = item_count - 1
            
            self.report({'WARNING'}, "JSONが読み込まれていません。基本モードで追加しました。")
            return {'FINISHED'}

#  　 　　Commandリストの削除
class Voice_OT_command_remove(bpy.types.Operator):
    bl_idname = "voice.command_remove"
    bl_label = "アイテム削除"

    def execute(self, context):
        scene = context.scene
        
        # bvc_command_propsから削除を試行
        if hasattr(scene, 'bvc_command_props') and hasattr(scene.bvc_command_props, 'language_commands'):
            command_props = scene.bvc_command_props
            current_language = command_props.current_language
            
            if current_language:
                for lang_item in command_props.language_commands:
                    if lang_item.language_name == current_language:
                        if len(lang_item.commands) > 0:
                            # アクティブなコマンドのインデックスを取得
                            active_cmd_idx = getattr(lang_item, 'active_command', 0)
                            if 0 <= active_cmd_idx < len(lang_item.commands):
                                removed_cmd = lang_item.commands[active_cmd_idx]
                                lang_item.commands.remove(active_cmd_idx)
                                
                                # アクティブインデックスを調整
                                if hasattr(lang_item, 'active_command'):
                                    lang_item.active_command = min(active_cmd_idx, len(lang_item.commands) - 1)
                                
                                # command_itemsからも対応するアイテムを削除
                                if hasattr(scene, 'command_items') and len(scene.command_items) > scene.command_index >= 0:
                                    scene.command_items.remove(scene.command_index)
                                    scene.command_index = min(scene.command_index, len(scene.command_items) - 1)
                                
                                self.report({'INFO'}, f"コマンド '{removed_cmd.command_key}' を削除しました")
                                return {'FINISHED'}
                            else:
                                self.report({'WARNING'}, "削除するコマンドが選択されていません")
                                return {'CANCELLED'}
                        else:
                            self.report({'WARNING'}, "削除するコマンドがありません")
                            return {'CANCELLED'}
                        break
                
                self.report({'ERROR'}, f"言語 '{current_language}' が見つかりません")
                return {'CANCELLED'}
        
        # フォールバック: command_itemsから削除
        if hasattr(scene, 'command_items'):
            if len(scene.command_items) > 0 and 0 <= scene.command_index < len(scene.command_items):
                scene.command_items.remove(scene.command_index)
                scene.command_index = min(scene.command_index, len(scene.command_items) - 1)
                self.report({'WARNING'}, "基本モードでアイテムを削除しました")
                return {'FINISHED'}
            else:
                self.report({'WARNING'}, "削除するアイテムがありません")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "command_items プロパティが初期化されていません")
            return {'CANCELLED'}

###########################################
#   　 　　言語別コマンドUI管理　
###########################################

class VOICE_OT_select_language(bpy.types.Operator):
    """言語を選択してコマンドリストを更新"""
    bl_idname = "voice.select_language"
    bl_label = "言語選択"
    bl_description = "選択した言語のコマンドリストを表示します"
    bl_options = {'REGISTER', 'UNDO'}
    
    language_name: bpy.props.StringProperty(name="Language Name", default="", options={"HIDDEN"})

    def execute(self, context):
        scene = context.scene
        
        # 現在の言語の編集内容を保存してから言語切り替え
        from .util import sync_command_items_to_bvc_props
        if hasattr(scene, 'bvc_command_props') and scene.bvc_command_props.current_language:
            if sync_command_items_to_bvc_props():
                print(f"切り替え前の言語【{scene.bvc_command_props.current_language}】の編集内容を保存しました")
        
        # コマンド編集欄をクリア
        if hasattr(scene, 'command_items'):
            scene.command_items.clear()
            scene.command_index = 0
        
        # 選択された言語のコマンドのみを追加
        if hasattr(scene, 'bvc_command_props') and hasattr(scene.bvc_command_props, 'language_commands'):
            command_props = scene.bvc_command_props
            added_count = 0
            
            try:
                for lang_item in command_props.language_commands:
                    if lang_item.language_name == self.language_name:
                        for cmd_item in lang_item.commands:
                            # 新しいアイテムを追加
                            new_item = scene.command_items.add()
                            
                            # 修正後
                            new_item.name = cmd_item.command_key
                            new_item.description = cmd_item.command_description
                            new_item.code = getattr(cmd_item, "command_code", f"# {lang_item.language_name}: {cmd_item.command_key}\nprint('【{lang_item.language_name}】{cmd_item.command_key}: {cmd_item.command_description}')")
                                                        
                            if hasattr(new_item, 'value'):
                                new_item.value = len(scene.command_items)
                            
                            added_count += 1
                        break
                
                if added_count > 0:
                    scene.command_index = 0
                    # 選択された言語を記録
                    command_props.current_language = self.language_name
                    self.report({'INFO'}, f"【{self.language_name}】から {added_count} 個のコマンドを表示しました")
                else:
                    self.report({'WARNING'}, f"【{self.language_name}】にコマンドが見つかりませんでした")
                    
            except Exception as e:
                self.report({'ERROR'}, f"言語選択エラー: {str(e)}")
                return {'FINISHED'}
        else:
            self.report({'WARNING'}, "JSONデータが読み込まれていません")
        
        return {'FINISHED'}

###########################################
#   　 　　JSONコマンド管理操作
###########################################
#   　 　　JSONコマンドの再読み込み
class VOICE_OT_reload_commands(bpy.types.Operator):
    """JSONファイルからコマンドを再読み込み"""
    bl_idname = "voice.reload_commands"
    bl_label = "コマンド再読み込み"
    bl_description = "JSONファイルからコマンドデータを再読み込みし、コマンド編集欄に適用します"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        
        # まずJSONファイルを読み込み
        from .util import load_commands_from_json
        if not load_commands_from_json():
            self.report({'ERROR'}, "JSONファイルの読み込みに失敗しました")
            return {'FINISHED'}
        
        # コマンド編集欄（command_items）をクリア
        if hasattr(scene, 'command_items'):
            scene.command_items.clear()
            scene.command_index = 0
        
        # 現在選択中の言語を保持、なければ最初の言語を選択
        if hasattr(scene, 'bvc_command_props') and hasattr(scene.bvc_command_props, 'language_commands'):
            command_props = scene.bvc_command_props
            
            if len(command_props.language_commands) > 0:
                # 現在選択中の言語を確認
                current_language = getattr(command_props, 'current_language', '')
                target_language = None
                target_lang_item = None
                
                # 現在選択中の言語が存在するかチェック
                if current_language:
                    for lang_item in command_props.language_commands:
                        if lang_item.language_name == current_language:
                            target_language = current_language
                            target_lang_item = lang_item
                            break
                
                # 現在選択中の言語が見つからない場合は最初の言語を使用
                if not target_language:
                    target_language = command_props.language_commands[0].language_name
                    target_lang_item = command_props.language_commands[0]
                    command_props.current_language = target_language
                
                # 選択された言語のコマンドをcommand_itemsに追加
                added_count = 0
                try:
                    for cmd_item in target_lang_item.commands:
                        # 新しいアイテムを追加
                        new_item = scene.command_items.add()
                        
                        # 修正後
                        new_item.name = cmd_item.command_key
                        new_item.description = cmd_item.command_description
                        new_item.code = getattr(cmd_item, "command_code", f"# {lang_item.language_name}: {cmd_item.command_key}\nprint('【{lang_item.language_name}】{cmd_item.command_key}: {cmd_item.command_description}')")

                        if hasattr(new_item, 'value'):
                            new_item.value = len(scene.command_items)
                        
                        added_count += 1
                    
                    if added_count > 0:
                        scene.command_index = 0
                        # 現在の言語が保持されたかどうかを表示
                        if current_language and target_language == current_language:
                            self.report({'INFO'}, f"JSONを読み込み、現在の言語【{target_language}】の {added_count} 個のコマンドを表示しました")
                        else:
                            self.report({'INFO'}, f"JSONを読み込み、【{target_language}】の {added_count} 個のコマンドを表示しました（初期言語）")
                    else:
                        self.report({'WARNING'}, "表示するコマンドがありませんでした")
                        
                except Exception as e:
                    self.report({'ERROR'}, f"コマンド表示エラー: {str(e)}")
                    return {'FINISHED'}
            else:
                self.report({'WARNING'}, "読み込まれた言語データがありません")
        else:
            self.report({'INFO'}, "JSONデータを読み込みました")
        
        return {'FINISHED'}
    
#   　 　　JSONコマンドの保存
class VOICE_OT_save_commands(bpy.types.Operator):
    """コマンドをJSONファイルに保存"""
    bl_idname = "voice.save_commands"
    bl_label = "コマンド保存"
    bl_description = "現在のコマンドデータをJSONファイルに保存します"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 保存前に、command_itemsからbvc_command_propsに自動同期
        from .util import sync_command_items_to_bvc_props, save_commands_to_json
        
        # まず同期を実行
        sync_success = sync_command_items_to_bvc_props()
        if sync_success:
            print("✅ 編集内容を自動同期しました")
        else:
            print("⚠️ 同期に失敗しましたが、保存を続行します")
        
        # JSON保存を実行
        if save_commands_to_json():
            if sync_success:
                self.report({'INFO'}, "編集内容を同期してJSONに保存しました")
            else:
                self.report({'INFO'}, "JSONに保存しました（同期は失敗）")
        else:
            self.report({'ERROR'}, "JSONの保存に失敗しました")
        return {'FINISHED'}

#   　 　　JSONファイルのデータとコマンドの同期
class VOICE_OT_sync_commands(bpy.types.Operator):
    """コマンド編集内容をJSONデータに手動同期"""
    bl_idname = "voice.sync_commands"
    bl_label = "編集内容を同期"
    bl_description = "編集したコマンド内容をJSONデータに手動同期（JSONに保存で自動実行されます）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from .util import sync_command_items_to_bvc_props
        
        if sync_command_items_to_bvc_props():
            self.report({'INFO'}, "編集内容を手動同期しました")
        else:
            self.report({'ERROR'}, "編集内容の同期に失敗しました")
        
        return {'FINISHED'}

class VOICE_OT_edit_command_inline(bpy.types.Operator):
    """コードを編集ダイアログで編集"""
    bl_idname = "voice.edit_command_inline"
    bl_label = "コード編集"
    bl_description = "コードを編集します"
    bl_options = {'REGISTER', 'UNDO'}
    
    item_index : bpy.props.IntProperty()
    
    # 編集用プロパティ
    edit_name : bpy.props.StringProperty(name="コマンド名")
    edit_description : bpy.props.StringProperty(name="説明")
    edit_code : bpy.props.StringProperty(name="コード")

    def invoke(self, context, event):
        # 現在の値を取得
        scene = context.scene
        if hasattr(scene, 'command_items') and len(scene.command_items) > self.item_index:
            item = scene.command_items[self.item_index]
            self.edit_name = item.name
            self.edit_description = item.description
            self.edit_code = item.code
        
        # 編集ダイアログを表示
        return context.window_manager.invoke_props_dialog(self, width=600)

    def draw(self, context):
        layout = self.layout
        
        layout.label(text="コマンド編集", icon='GREASEPENCIL')
        layout.separator()
        
        # 編集フィールド
        layout.prop(self, "edit_name")
        layout.prop(self, "edit_description")
        
        # コード編集エリア（複数行対応）
        box = layout.box()
        col = box.column()
        col.label(text="コード:")
        col.prop(self, "edit_code", text="")

    def execute(self, context):
        # 変更を保存
        scene = context.scene
        if hasattr(scene, 'command_items') and len(scene.command_items) > self.item_index:
            item = scene.command_items[self.item_index]
            item.name = self.edit_name
            item.description = self.edit_description
            item.code = self.edit_code
            
            self.report({'INFO'}, f"コマンド '{item.name}' を更新しました")
        
        return {'FINISHED'}

class VOICE_OT_execute_command_popup(bpy.types.Operator):
    """ポップアップからコマンドを実行"""
    bl_idname = "voice.execute_command_popup"
    bl_label = "コマンド実行"
    bl_description = "コマンドを実行します"
    bl_options = {'REGISTER', 'UNDO'}
    
    item_index : bpy.props.IntProperty()

    def execute(self, context):
        scene = context.scene
        if hasattr(scene, 'command_items') and len(scene.command_items) > self.item_index:
            item = scene.command_items[self.item_index]
            
            try:
                if item.code.strip():
                    # 危険なコードの基本チェック
                    dangerous_functions = ['import os', 'import sys', 'open(', 'file(', 'exec(', 'eval(']
                    code_lower = item.code.lower()
                    
                    for danger in dangerous_functions:
                        if danger in code_lower:
                            self.report({'ERROR'}, f"安全上の理由により実行できません: '{danger}' が含まれています")
                            return {'CANCELLED'}
                    
                    # Blenderのグローバル環境を含めて実行
                    exec_globals = {
                        'bpy': bpy,
                        'bmesh': None,  # 必要に応じてimport
                        '__builtins__': __builtins__
                    }
                    
                    # 追加で利用可能なライブラリを設定
                    try:
                        import mathutils
                        exec_globals['mathutils'] = mathutils
                    except ImportError:
                        pass
                    
                    try:
                        import math
                        exec_globals['math'] = math
                    except ImportError:
                        pass
                        
                    try:
                        import random
                        exec_globals['random'] = random
                    except ImportError:
                        pass
                    
                    # bmeshが必要かチェック
                    if 'bmesh' in item.code:
                        import bmesh
                        exec_globals['bmesh'] = bmesh
                    
                    print(f"🎯 実行開始: {item.name}")
                    print(f"📋 コード:\n{item.code}")
                    
                    # コードを実行
                    exec(item.code, exec_globals)
                    
                    # 画面を更新
                    for area in context.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                    
                    # 成功メッセージ
                    self.report({'INFO'}, f"✅ コマンド '{item.name}' を実行しました")
                    print(f"✅ 実行完了: {item.name}")
                    
                else:
                    self.report({'WARNING'}, "実行するコードがありません")
            except Exception as e:
                error_msg = f"実行エラー: {str(e)}"
                self.report({'ERROR'}, error_msg)
                print(f"❌ {error_msg}")
                print(f"📋 エラーが発生したコード:\n{item.code}")
        
        return {'FINISHED'}

##############################################
#  　 　　音声識別
##############################################
# 音声デバイスをチェック（Operator版）
class VOICE_OT_speech_recognition(Operator):
    """音声録音を実行するオペレーター"""
    bl_idname = "voice.speech_recognition"
    bl_label = "音声識別"
    bl_description = "音声識別の開始/停止"
    bl_options = {'REGISTER','UNDO'}
    
    def execute(self, context):
        return self.recording_with_device_check()
    
    def recording_with_device_check(self):
        """音声デバイスをチェックして録音を実行"""
        self.report({'INFO'}, "🔍 音声デバイスをチェック中...")

        # デバイスのチェック
        selected_device = check_audio_devices()
        
        if selected_device is None:
            self.report({'WARNING'}, "⚠️ デフォルトデバイスを試します")
        else:
            # 選択されたデバイスをテスト
            self.report({'INFO'}, f"🧪 選択されたデバイス {selected_device} をテスト中...")
            if not test_audio_device(selected_device):
                self.report({'ERROR'}, "❌ 選択されたデバイスが使用できません")
                
                # 他のデバイスも試してみる
                self.report({'INFO'}, "🔄 他の利用可能デバイスを試しています...")
                devices = sd.query_devices()
                input_devices = [i for i, d in enumerate(devices) if d['max_input_channels'] > 0]
                
                found_working_device = False
                for device_id in input_devices:
                    if device_id != selected_device:
                        self.report({'INFO'}, f"🧪 デバイス {device_id} ({devices[device_id]['name']}) をテスト中...")
                        if test_audio_device(device_id):
                            selected_device = device_id
                            found_working_device = True
                            self.report({'INFO'}, f"✅ デバイス {device_id} が動作しました")
                            break
                
                if not found_working_device:
                    self.report({'ERROR'}, "❌ 動作する音声デバイスが見つかりませんでした")
                    self.report({'ERROR'}, "🛠️ マイクが接続されているか確認してください")
                    return {'CANCELLED'}
        
        try:
            # 音声認識部分
            self.report({'INFO'}, "🎙️ 音声入力を開始します...")
            with sd.InputStream(
                callback=callback, 
                channels=1, 
                samplerate=16000,
                device=selected_device
            ):
                # Blender UIをブロックしないように、短時間の録音に変更
                print("🎤 録音中... (5秒間)")
                sd.sleep(5000)  # 5秒録音
                recognize_from_queue()  # 定期的にキューから音声を取り出し認識
            
            self.report({'INFO'}, "✅ 音声録音が完了しました")
            return {'FINISHED'}
            
        except Exception as e:
            error_msg = f"❌ 音声入力エラー: {e}"
            self.report({'ERROR'}, error_msg)
            self.report({'ERROR'}, "🛠️ 対処法:")
            self.report({'ERROR'}, "1. マイクが接続されているか確認してください")
            self.report({'ERROR'}, "2. Windowsの音声設定でマイクが有効になっているか確認してください")
            self.report({'ERROR'}, "3. 他のアプリケーションがマイクを使用していないか確認してください")
            return {'CANCELLED'}
        

##############################################
#  　 　　チェックボックスの値が変わったときに呼ばれるOperator
##############################################
class VOICE_OT_language_check(Operator):
    bl_idname = "voice.language_check"
    bl_label = "言語選択"
    bl_description = "言語設定を選択したもの以外をクリア"
    bl_options = {'REGISTER','UNDO'}

    """executeを別の関数から呼び出す際は、別の関数内で引数にプロパティが必要になる"""
    # ✅ bpy.opsを通して呼び出す（引数はプロパティで渡す）
    # 押されたチェックボックスのキーを受け取るプロパティ
    pressed_key: bpy.props.StringProperty(
        name="押されたキー",
        description="押されたチェックボックスのキー (JA, EN, ZH)",
        default=""
    )

    def execute(self,context):
        props = bpy.context.scene.bvc_language_props

        # 押されたキーを取得
        if not self.pressed_key:
            print("❌ 押されたキーが指定されていません")
            return {'CANCELLED'}
        
        key = self.pressed_key
        print(f"🖱️ 押されたチェックボックスのキー: {key}")

        # 押されたキーの現在の状態を確認
        check_flag = getattr(props, key, None)

        if check_flag is True:
            setattr(props, key, False)
            print(f"❌ {key} をFalseに変更しました")

        elif check_flag is False:
            # False → True: すべてをFalseにしてから選択したもののみTrue
            print(f"📋 排他的選択を実行: {key} のみTrueにします")
            #すべてのチェックを外す
            for other_key, label in props.language_keys:
                setattr(props, other_key, False)
                print(f"   ❌ {other_key} → False")
            #選択したものだけTrueにする
            setattr(props, key, True)
            print(f"   ✅ {key} → True")

        else:
            #選択したチェックボックスがTrueでもFalseでもない場合
            # None または異常値の場合
            print(f"⚠️ {key} の状態が異常です: {check_flag}")
            pass
        
        return {'FINISHED'}
    

###########################################
#   　 　　ボリューム閾値説明オペレーター
###########################################
class VOICE_OT_volume_threshold_info(Operator):
    bl_idname = "voice.volume_threshold_info"
    bl_label = "ボリューム閾値について"
    bl_description = "ボリューム閾値の詳細説明を表示"
    bl_options = {'REGISTER'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        # ポップアップダイアログを表示
        return context.window_manager.invoke_popup(self, width=400)

    def draw(self, context):
        layout = self.layout
        
        # タイトル
        row = layout.row()
        row.alignment = 'CENTER'
        row.label(text="🔊 ボリューム閾値の設定", icon='OUTLINER_OB_SPEAKER')
        
        layout.separator()
        
        # 説明文
        box = layout.box()
        col = box.column(align=True)
        col.label(text="📋 概要:")
        col.label(text="  音声認識を開始する最小音量レベルを設定します")
        col.label(text="  値が小さいほど小さな音でも反応します")
        
        layout.separator()
        
        box = layout.box()
        col = box.column(align=True)
        col.label(text="🎚️ 推奨設定:")
        col.label(text="  • 0.1 - 0.3: 静かな環境での使用")
        col.label(text="  • 0.3 - 0.5: 標準的な環境での使用")
        col.label(text="  • 0.5 - 0.8: 騒がしい環境での使用")
        
        layout.separator()
        
        box = layout.box()
        col = box.column(align=True)
        col.label(text="⚠️ 注意点:")
        col.label(text="  • 値が低すぎると雑音でも反応します")
        col.label(text="  • 値が高すぎると音声を検出できません")
        col.label(text="  • マイクの性能により適切な値が異なります")
        
        layout.separator()
        
        box = layout.box()
        col = box.column(align=True)
        col.label(text="💡 調整方法:")
        col.label(text="  1. 通常の声の大きさで話す")
        col.label(text="  2. 認識が開始される値まで調整")
        col.label(text="  3. 雑音で誤作動しない値を確認")
        
        # 現在の設定値を表示
        if hasattr(context.scene, 'bvc_device_props'):
            props = context.scene.bvc_device_props
            layout.separator()
            row = layout.row()
            row.alignment = 'CENTER'
            row.label(text=f"現在の設定: {props.volume_threshold:.2f}", icon='INFO')

###########################################
#   　 　　録音デバイス説明オペレーター
###########################################
class VOICE_OT_device_info(Operator):
    bl_idname = "voice.device_info"
    bl_label = "録音デバイスについて"
    bl_description = "録音デバイスの詳細説明を表示"
    bl_options = {'REGISTER'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        # ポップアップダイアログを表示
        return context.window_manager.invoke_popup(self, width=400)

    def draw(self, context):
        layout = self.layout
        
        # タイトル
        row = layout.row()
        row.alignment = 'CENTER'
        row.label(text=" 録音デバイスの設定", icon='TOOL_SETTINGS')
        
        layout.separator()
        
        # 説明文
        box = layout.box()
        col = box.column(align=True)
        col.label(text="⚠️ 注意点:")
        col.label(text="  Blenderの仕様上、録音デバイスの変更はBlender再起動後に反映されます")
        col.label(text="  そのため、デバイスを変更した場合はBlenderを再起動してください")
        
###########################################
#   　 　　コマンド編集説明オペレーター
###########################################
class VOICE_OT_command_info(Operator):
    bl_idname = "voice.command_info"
    bl_label = "コマンド編集について"
    bl_description = "コマンド編集の詳細説明を表示"
    bl_options = {'REGISTER'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        # ポップアップダイアログを表示
        return context.window_manager.invoke_popup(self, width=400)

    def draw(self, context):
        layout = self.layout
        
        # タイトル
        row = layout.row()
        row.alignment = 'CENTER'
        row.label(text=" コマンド編集の設定", icon='TOOL_SETTINGS')
        
        layout.separator()
        
        # 説明文
        box = layout.box()
        col = box.column(align=True)
        col.label(text="⚠️ 注意点:")
        col.label(text="BVCでは、システム破壊の防止やデータ保護のため、")
        col.label(text="音声コマンドによる危険なコードの実行を制限しています")

        layout.separator()
        
        box = layout.box()
        col = box.column(align=True)
        col.label(text="利用不可能なコード:")
        col.label(text="  1. import os - システム操作が可能")
        col.label(text="  2. import sys - Pythonシステム制御")
        col.label(text="  3. open( - ファイル操作")
        col.label(text="  4. file( - ファイルアクセス（Python2系）")
        col.label(text="  5. exec( - 任意のコード実行")
        
       
        

        









    