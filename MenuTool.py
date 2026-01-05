import bpy
from bpy.types import Operator,Menu
from .OperatorTool import *
from .util import *
from .BVCProperties import *

######################################
#  　 　　言語選択UIメニュー　     
######################################
class VOICE_MT_language_select(Menu):

    bl_idname = "VOICE_MT_language_select"
    bl_label = "言語選択"
    bl_description = "表示する言語を選択"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # 各言語の選択肢のみ表示
        if hasattr(scene, 'bvc_command_props') and hasattr(scene.bvc_command_props, 'language_commands'):
            command_props = scene.bvc_command_props
            current_lang = getattr(command_props, 'current_language', '未選択')
            
            for lang_item in command_props.language_commands:
                button_text = f"{lang_item.language_name} ({len(lang_item.commands)})"
                icon = 'DOT' if current_lang == lang_item.language_name else 'NONE'
                op = layout.operator("voice.select_language", text=button_text, icon=icon)
                op.language_name = lang_item.language_name
        else:
            layout.label(text="言語データがありません", icon='INFO')

######################################
#  　 　　選択デバイスUIメニュー　     
######################################
#音声デバイスの設定
class VOICE_MT_search_device(Menu):

    bl_idname = "VOICE_MT_search_device"
    bl_label = "音声デバイス"
    bl_description = "使用可能な録音デバイスの更新"
            
    def draw(self,context):
        """
        【警告】Blenderの仕様上、draw()メソッド（UI描画時）ではデータの追加・変更（add, remove, 値の書き換え）はできません。
        """
        draw_layout = self.layout
        props = bpy.context.scene.bvc_device_props
        for item in props.device_list:
            op = draw_layout.operator(VOICE_OT_search_device.bl_idname, text=item.device_name)
            op.device_name = item.device_name

    


    
 