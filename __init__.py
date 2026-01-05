# 利用するタイプやメソッドのインポート
import bpy
from bpy.types import Operator, Panel
from .PanelTool import *
from .OperatorTool import *
#from .BVCProperties import *
from .BVCProperties import (
    Device_Name,
    Voice_Command_Item,
    Language_Commands,
    BVC_Device_Properties,
    BVC_Mode_Properties,
    BVC_Command_Properties,
    BVC_Language_Properties,
    CommandItem,
    #MyItem
)

import sounddevice as sd
#from .util import *
from .util import get_unique_mics
try:
    import pywhispercpp
    print("pywhispercpp は Blender で使用可能です")
except ImportError:
    print("pywhispercpp は Blender で使用できません")
# bl_infoでプラグインに関する情報の定義を行う
bl_info = {
    "name": "Blender Voice Command(BVC)",                # プラグイン名
    "author": "Kozuki Tomoya",                             # 制作者名
    "version": (1, 0, 1),                                   # バージョン
    "blender": (4, 00, 0),                           # 動作可能なBlenderバージョン
    "support": "TESTING",                            # サポートレベル(OFFICIAL,COMMUNITY,TESTING)
    "category": "3D View",                           # カテゴリ名
    "location": "View3D > Sidebar > BVC",      # ロケーション
    "description": "音声認識による操作を支援するアドオン",                  # 説明文
    "location": "",                                  # 機能の位置付け
    "warning": "",                                   # 注意点やバグ情報
    "doc_url": "",                                   # ドキュメントURL
}


# 登録対象のクラス名
regist_classes = (
    Device_Name,
    Voice_Command_Item,
    Language_Commands,
    BVC_Device_Properties,
    BVC_Mode_Properties,
    BVC_Command_Properties,
    BVC_Language_Properties,
    CommandItem,

    VOICE_PT_bvc_mode,
    VOICE_PT_device_setting,
    VOICE_PT_command_setting,
    Command_UL_items,

    VOICE_OT_bvc_mode,
    VOICE_OT_search_device,
    VOICE_OT_update_device_list,
    VOICE_OT_language_clear,
    VOICE_OT_language_all,
    VOICE_OT_language_check,
    Voice_OT_command_add,
    Voice_OT_command_remove,
    VOICE_OT_reload_commands,
    VOICE_OT_save_commands,
    VOICE_OT_sync_commands,
    VOICE_OT_select_language,
    VOICE_OT_edit_command_inline,
    VOICE_OT_execute_command_popup,
    VOICE_OT_volume_threshold_info,
    VOICE_OT_device_info,
    VOICE_OT_command_info,

    VOICE_MT_language_select,
    VOICE_MT_search_device,
)

def register():
    print("VoiceCommand アドオンの登録を開始します...")
    # すべてのクラスを登録
    for cls in regist_classes:
        try:
            bpy.utils.register_class(cls)
            print(f"クラス {cls.__name__} を登録しました")
        except Exception as e:
            print(f"クラス {cls.__name__} の登録に失敗: {e}")
            return
    
    # プロパティをシーンに一括追加
    try:
        # PointerProperty（単一プロパティ）の登録
        bpy.types.Scene.bvc_device_props = bpy.props.PointerProperty(type=BVC_Device_Properties)
        bpy.types.Scene.bvc_mode_props = bpy.props.PointerProperty(type=BVC_Mode_Properties)
        bpy.types.Scene.bvc_command_props = bpy.props.PointerProperty(type=BVC_Command_Properties)
        bpy.types.Scene.bvc_language_props = bpy.props.PointerProperty(type=BVC_Language_Properties)
        
        # CollectionProperty（コレクションプロパティ）の登録
        bpy.types.Scene.command_items = bpy.props.CollectionProperty(type=CommandItem)
        bpy.types.Scene.command_index = bpy.props.IntProperty(name="Command Index", default=0)

        
        print("すべてのプロパティを正常に登録しました")
    except Exception as e:
        print(f"プロパティの登録に失敗: {e}")
        return
    
    # JSONコマンド読み込みを遅延実行（コンテキストが利用可能になってから）
    def delayed_json_load():
        try:
            from .util import load_commands_from_json
            if load_commands_from_json():
                print("JSONコマンドデータを読み込みました")
            else:
                print("JSONコマンドデータの読み込みをスキップしました")
        except Exception as e:
            print(f"JSONコマンドデータの読み込みに失敗: {e}")
        return None  # タイマーを停止
    
    # 0.5秒後に実行するタイマーを設定（初期化をより確実に待つ）
    bpy.app.timers.register(delayed_json_load, first_interval=0.5)
    

# 作成クラスと定義の登録解除メソッド
def unregister():
    # プロパティを削除
    try:
        # PointerProperty（単一プロパティ）の削除
        del bpy.types.Scene.bvc_device_props
        del bpy.types.Scene.bvc_mode_props
        del bpy.types.Scene.bvc_command_props
        del bpy.types.Scene.bvc_language_props
        
        # CollectionProperty（コレクションプロパティ）の削除
        del bpy.types.Scene.command_items
        del bpy.types.Scene.command_index
    except AttributeError:
        pass
    
    # カスタムクラスを解除する
    for regist_cls in reversed(regist_classes):
        try:
            bpy.utils.unregister_class(regist_cls)
        except Exception:
            pass

# プロパティを削除
def clear_props():
    scene = bpy.types.Scene
    del scene.device_enum
# エディター実行時の処理
if __name__ == "__main__":
    # 作成クラスと定義を登録する
    
    register()