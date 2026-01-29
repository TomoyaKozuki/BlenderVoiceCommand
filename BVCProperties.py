import bpy
from .util import *
#from .OperatorTool import *
class Device_Name(bpy.types.PropertyGroup):
    device_name: bpy.props.StringProperty(name="Device_Name：デバイス名")

######################################
#  　 　　デバイスプロパティ　     
######################################
class BVC_Device_Properties(bpy.types.PropertyGroup):
    #音量のパラメータ
    volume_threshold:bpy.props.FloatProperty(
        name="Volume_threshold",
        description="Volume level",
        default=0.5,
        min=0.0,
        max=1.0
    )

    #デバイス名のリスト と 選択されたデバイス名
    device_list:bpy.props.CollectionProperty(type=Device_Name)
    selected_device:bpy.props.StringProperty(name="選択されたデバイス",default="未選択")


######################################
#  　 　　音声識別状態プロパティ     
######################################
class BVC_Mode_Properties(bpy.types.PropertyGroup):

    mode: bpy.props.EnumProperty(
        name="BVC Mode",
        description="Current BVC mode",
        #ここをjsonファイルから読み込んだ値を設定する
        items=[
            ('UNSET', "マイク未設定", ""),
            ('IDLE', "待機中", ""),
            ('RECOGNIZING', "認識中", ""),
            ('MUTED', "ミュート中", "")
        ],
        default='UNSET'
    )

######################################
#  　 　　コマンドリスト要素プロパティ　     
######################################
# リスト要素
class CommandItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="コマンド名")
    description: bpy.props.StringProperty(name="処理内容の説明")
    code: bpy.props.StringProperty(name="処理コード")
######################################
#  　 　　言語別コマンドのプロパティ　     
##########################################
class Voice_Command_Item(bpy.types.PropertyGroup):
    """個別の音声コマンドアイテム"""
    command_key : bpy.props.StringProperty(
        name="コマンドキー",
        description="音声コマンドのキー（例：保存、削除）"
    )
    command_description : bpy.props.StringProperty(
        name="コマンド説明",
        description="コマンドの説明文"
    )
    command_code : bpy.props.StringProperty(
        name="コマンドコード",
        description="音声コマンドのコード（例：save_command、delete_command）"
    )
######################################
#  　 　　言語別コマンドのプロパティ　     
######################################
class Language_Commands(bpy.types.PropertyGroup):
    """言語別のコマンドリスト"""
    language_name : bpy.props.StringProperty(
        name="言語名",
        description="言語名（例：日本語、English）"
    )
    commands : bpy.props.CollectionProperty(
        type=Voice_Command_Item,
        name="コマンドリスト"
    )
    active_command : bpy.props.IntProperty(
        name="アクティブコマンド",
        description="現在選択されているコマンドのインデックス"
    )

######################################
#  　 　　メインのコマンド管理プロパティ     
######################################
class BVC_Command_Properties(bpy.types.PropertyGroup):
    command_dicts :  bpy.props.EnumProperty(
        name="BVC Command",
        description="Current BVC command",
        items=[
            #('コマンド名','識別音声')
            ('SAVE', "保存", ""),
            ('IDLE', "待機中", ""),
            ('RECOGNIZING', "認識中", ""),
            ('MUTED', "ミュート中", "")
        ],
        default='IDLE'
    )
    
    # 新しいJSONベースのコマンド管理
    language_commands : bpy.props.CollectionProperty(
        type=Language_Commands,
        name="言語別コマンド"
    )
    
    active_language : bpy.props.IntProperty(
        name="アクティブ言語",
        description="現在選択されている言語のインデックス"
    )
    
    # 現在表示中の言語を記録
    current_language : bpy.props.StringProperty(
        name="現在の言語",
        description="現在コマンド編集欄に表示されている言語",
        default="未選択"
    )
    
    # JSONファイルパス
    json_file_path : bpy.props.StringProperty(
        name="JSONファイルパス",
        description="音声コマンドJSONファイルのパス",
        default="command.json"
    )
######################################
#  チェックボックスの値が変わった瞬間の処理
######################################
def ja_checkbox_update(self, context):
    """日本語チェックボックスが押された時"""
    if hasattr(self, '_updating'):
        return
    
    print("日本語チェックボックスが押されました")
    
    if getattr(self, "JA", False):  # JAがTrueになった場合のみ
        try:
            self._updating = True
            print("排他的選択を実行: JA のみTrueにします")
            # 他をすべてFalseにする（setattr使用）
            setattr(self, "EN", False)
            setattr(self, "ZH", False)
            print("   EN → False")
            print("   ZH → False")
            print("   JA → True")
        finally:
            if hasattr(self, '_updating'):
                delattr(self, '_updating')

def en_checkbox_update(self, context):
    """英語チェックボックスが押された時"""
    if hasattr(self, '_updating'):
        return
    
    print("英語チェックボックスが押されました")
    
    if getattr(self, "EN", False):  # ENがTrueになった場合のみ
        try:
            self._updating = True
            print("排他的選択を実行: EN のみTrueにします")
            setattr(self, "JA", False)
            setattr(self, "ZH", False)
            print("   JA → False")
            print("   ZH → False")
            print("   EN → True")
        finally:
            if hasattr(self, '_updating'):
                delattr(self, '_updating')

def zh_checkbox_update(self, context):
    """中文チェックボックスが押された時"""
    if hasattr(self, '_updating'):
        return
    
    print("中文チェックボックスが押されました")
    
    if getattr(self, "ZH", False):  # ZHがTrueになった場合のみ
        try:
            self._updating = True
            print("排他的選択を実行: ZH のみTrueにします")
            setattr(self, "JA", False)
            setattr(self, "EN", False)
            print("   JA → False")
            print("   EN → False")
            print("   ZH → True")
        finally:
            if hasattr(self, '_updating'):
                delattr(self, '_updating')

######################################
#  　 　　言語プロパティ　     
######################################
class BVC_Language_Properties(bpy.types.PropertyGroup):
    # クラス変数として定義
    language_keys = [
        ("JA", "日本語"),
        ("EN", "English"),
        #("ES", "Español"),
        #("FR", "Français"),
        #("DE", "Deutsch"),
        #("IT", "Italiano"),
        ("ZH", "中文"),
        #("KO", "한국어"),
    ]

    
    ###################################################
    # 言語リストのBoolProperty定義　
    ###################################################
    JA: bpy.props.BoolProperty(name="日本語",update=ja_checkbox_update,default=False)
    EN: bpy.props.BoolProperty(name="English",update=en_checkbox_update,default=False)
    #ES: bpy.props.BoolProperty(name="Español",default=False,update=checkbox_update)
    #FR: bpy.props.BoolProperty(name="Français",default=False,update=checkbox_update)
    #DE: bpy.props.BoolProperty(name="Deutsch",default=False,update=checkbox_update)
    #IT: bpy.props.BoolProperty(name="Italiano",default=False,update=checkbox_update)
    ZH: bpy.props.BoolProperty(name="中文",update=zh_checkbox_update,default=False)
    #KO: bpy.props.BoolProperty(name="한국어",default=False,update=checkbox_update)



    language_items = language_keys.copy()
    for i, item in enumerate(language_items):
        item = list(item)
        item.append("")
        language_items[i] = tuple(item)