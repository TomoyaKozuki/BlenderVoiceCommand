# BlenderVoiceCommand
Blender Voice Control（BVC）は、**音声認識によって Blender を操作可能にするアドオン**です。

本アドオンは、従来のキーボードやマウスといった物理的 UI に依存せず、音声コマンドによってモデリングや操作を行う新しい入力手法の実現を目的として開発されました。

近年発展が進むVR/AR環境では、従来の入力デバイスによる操作が制限される場面が多く、  
将来的には音声操作が重要なインターフェースになると考えられます。BVCはその基礎的な試みとして、Blender上での音声操作を可能にします。

本アドオンでは以下の特徴を備えています。

- 音声認識による Blender 操作
- 日本語・英語・中国語の多言語対応
- ユーザーが自由に定義可能な音声コマンド
- Blender 内部 Python コードの実行による柔軟な拡張
- 録音デバイス・音量閾値の調整機能

研究用途から制作補助、将来的な VR/AR 制作環境への応用までを想定したアドオンです。
# Requirements
### blender & python
- blender 4.1
- blender python 3.11.7
  
### dependency
- pywhispercpp
- faster whisper
- numpy
- sounddevice
- janome

# Installation

1. Blender を起動します。
2. **Edit → Preferences → Add-ons** を開きます。
3. 上部のフィルターから **Testing** を選択します。
4. **Install…** をクリックし、`VoiceCommand.zip` を選択します。
5. アドオン一覧に表示される  
   **3D View: Blender Voice Command (BVC)** にチェックを入れて有効化します。

> ⚠️ Windows 環境では、Blender を **管理者権限で実行**してください。

# Usage

- Blender を **管理者権限で実行**します。
- 3D ビューポート上で **Nキー** を押し、サイドバーを表示します。
- **VoiceCommand** タブを選択します。
- 以下の設定を行います。
  - 録音デバイスの選択
  - 認識言語の選択
  - 音声コマンドの設定
- 音声認識を開始し、音声コマンドによって Blender を操作します。


# License
This repo is under the [MIT LICENSE](LICENSE).
