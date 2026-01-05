import bpy
from bpy.types import Operator, Panel
from .OperatorTool import *
from .MenuTool import *
from .BVCProperties import *
from .util import *

###########################################
#   　 　　音声認識のUI表示
###########################################
class VOICE_PT_bvc_mode(Panel):

    bl_label = "音声認識の実行"
    bl_idname = "VOICE_PT_bvc_mode"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = set()
    bl_order = 0
    bl_category = "VoiceCommand"
 
    # 描画の定義
    def draw(self, context):
        from .util import voice_manager
        draw_layout = self.layout
        # Operatorをボタンとして配置する
        draw_layout.label(text="音声認識", icon='SPEAKER')

        #言語の選択ボタン
        props = bpy.context.scene.bvc_language_props
        row_button = draw_layout.row()
        for key, label in props.language_keys:
            row_button.prop(props, key, text=label)
        
        # 詳細な状態情報を取得
        status_info = voice_manager.get_status_info()
        
        # 音声認識の状態を表示
        if status_info["is_active"]:
            # 録音中の表示
            row = draw_layout.row()
            row.alert = True  # 赤色で強調
            row.operator("voice.bvc_mode", text="🎤 録音中... (クリックで停止)", icon='REC')
            
            # 状態詳細を表示
            box = draw_layout.box()
            #box.label(text=f"デバイス: {status_info['current_device']}", icon='SOUND')
            
            # 認識言語を表示
            active_language_code = get_active_language()
            active_language_name = code_to_display_name(active_language_code)
            box.label(text=f"認識言語: {active_language_name}", icon='SOUND')
            # 実行時間を表示
            if "duration" in status_info:
                box.label(text=f"経過時間: {status_info['duration']}秒", icon='TIME')
            
            # 音声レベル表示を追加
            if "audio_level_indicator" in status_info:
                level_text = status_info["audio_level_indicator"]
                if level_text:
                    # 音声レベルを視覚的に表示
                    level_box = box.box()
                    level_row = level_box.row()
                    level_row.alignment = 'CENTER'
                    level_row.label(text=f"音声レベル: {level_text}", icon='SOUND')
            
            # 最新の認識結果があれば表示
            if status_info["last_result"] and "text" in status_info["last_result"]:
                text = status_info["last_result"]["text"]
                if len(text) > 25:
                    text = text[:25] + "..."
                box.label(text=f"認識結果: {text}", icon='TEXT')
            
            #volumeパラメータの表示
            if hasattr(bpy.context.scene, 'bvc_device_props'):
                props = bpy.context.scene.bvc_device_props
                box.label(text=f"音声閾値: {props.volume_threshold:.2f}")
                box.label(text=f"使用デバイス: {props.selected_device}")
            else:
                box.label(text="音声閾値: N/A")
                box.label(text="使用デバイス: N/A")
            # 停止方法を表示
            box.label(text="💡 ESCキーで停止", icon='INFO')
        else:
            # 待機中の表示
            draw_layout.operator("voice.bvc_mode", text="音声認識開始", icon='PLAY')
            
            # 状態メッセージを表示
            if status_info["status_message"] != "待機中":
                draw_layout.label(text=f"状態: {status_info['status_message']}", icon='ERROR')

###########################################
#   　 　　音声デバイスのUI表示
###########################################
class VOICE_PT_device_setting(Panel):
    mode = "待機中"
    bl_label = f"録音デバイスの設定"
    bl_idname = "VOICE_PT_device_setting"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = set()
    bl_order = 0
    bl_category = "VoiceCommand"
 
    # 描画の定義
    def draw(self, context):
        props = bpy.context.scene.bvc_device_props # PointerPropertyの参照を取得
        draw_layout = self.layout
        row = draw_layout.row()
        row.operator("voice.update_device_list", text="録音デバイスの検出",icon='FILE_REFRESH')
        row.operator("voice.device_info", text="", icon='INFO')
        draw_layout.menu(VOICE_MT_search_device.bl_idname, text=props.selected_device)#props.selected_device)#props.selected_device
        
        draw_layout.separator()

        row = draw_layout.row()
        row.label(text="ボリューム閾値の調整(0~1)", icon='OUTLINER_OB_SPEAKER')
        row.operator("voice.volume_threshold_info", text="", icon='INFO')
        draw_layout.prop(props, "volume_threshold", slider=True)
    

###########################################
#   　 　　音声コマンドのUI表示
###########################################
class VOICE_PT_command_setting(Panel):

    bl_label = "音声コマンドの設定"
    bl_idname = "VOICE_PT_command_setting"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = set()
    bl_order = 0
    bl_category = "VoiceCommand"
 
    # 描画の定義
    def draw(self, context):
        draw_layout = self.layout
        scene = context.scene
        
        # JSONファイル操作セクション
        draw_layout.label(text="コマンド情報の操作", icon='FILE_SCRIPT')
        row = draw_layout.row()
        row.operator("voice.reload_commands", text="コマンド情報の読み込み", icon='IMPORT')
        row.operator("voice.save_commands", text="コマンド情報の保存", icon='EXPORT')
        
        draw_layout.separator()
        
        # 現在選択中の言語を取得（デフォルト値付き）
        current_lang = '未選択'
        if hasattr(scene, 'bvc_command_props'):
            command_props = scene.bvc_command_props
            current_lang = getattr(command_props, 'current_language', '未選択')
        
        # 言語選択セクション（メニュー形式）
        if hasattr(scene, 'bvc_command_props'):
            command_props = scene.bvc_command_props
            
            if hasattr(command_props, 'language_commands') and len(command_props.language_commands) > 0:
                
                draw_layout.label(text="言語選択", icon='WORLD')
                
                # ドロップダウンメニュー
                draw_layout.menu("VOICE_MT_language_select", text=f"言語を選択 ({current_lang})")
                
                draw_layout.separator()
        
        # 従来のコマンド編集UIList
        row = draw_layout.row()
        row.label(text=f"コマンド編集: {current_lang}", icon='GREASEPENCIL')
        row.operator("voice.command_info", text="", icon='INFO')
        row = draw_layout.row()
        row.template_list(
            "Command_UL_items",        # UIList のクラス名
            "",                   # unique ID
            scene, "command_items",    # CollectionProperty
            scene, "command_index"     # active_index
        )

        col = row.column(align=True)
        col.operator(Voice_OT_command_add.bl_idname, icon='ADD', text="")    # ＋ボタン
        col.operator(Voice_OT_command_remove.bl_idname, icon='REMOVE', text="")  # －ボタン

            

###########################################
#   　 　　認識言語のUI表示
###########################################
class VOICE_PT_language_setting(Panel):

    bl_label = "音声言語の設定"
    bl_idname = "VOICE_PT_language_setting"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = set()
    bl_order = 0
    bl_category = "VoiceCommand"
 
    # 描画の定義
    def draw(self, context):
        layout = self.layout
        props = bpy.context.scene.bvc_language_props
        row_button = layout.row()
        for key, label in props.language_keys:
            row_button.prop(props, key, text=label)
        layout.separator()
        row = layout.row()
        row.alignment = 'EXPAND'
        row.operator(VOICE_OT_language_clear.bl_idname, text="clear")
        row.operator(VOICE_OT_language_all.bl_idname, text="all")
        pass

###########################################
#   　 　　commandパネルのUIList表示
###########################################
class Command_UL_items(bpy.types.UIList):
    # 1行ごとの描画内容を設定
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # 横一列に配置し、幅を適切に制御
            split = layout.split(factor=0.25)  # 25%の幅をnameに割り当て
            # nameプロパティ（左側、25%）
            col1 = split.column()
            col1.prop(item, "name", text="", emboss=False, icon='DOT')
            
            # descriptionとcodeプロパティ（中央、50%）
            split2 = split.split(factor=0.4)  # 残り75%の40%をdescriptionに
            col2 = split2.column()
            col2.prop(item, "description", text="")
            
            split3 = split2.split(factor=0.6)  # 残りの60%をcodeに
            col3 = split3.column()
            col3.prop(item, "code", text="")
            
            # ボタン列（右側、残りの空間）
            col4 = split3.column()
            row_buttons = col4.row(align=True)
            
            # 実行ボタンを追加
            row_buttons.operator("voice.execute_command_popup", text="", icon='PLAY').item_index = index
            
            # ポップアップ機能 - プロパティを直接指定
            row_buttons.operator("voice.edit_command_inline", text="", icon='GREASEPENCIL').item_index = index
            
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='DOT')

