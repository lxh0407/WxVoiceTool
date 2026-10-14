# 微信语音提取器 · WxVoiceTool

从本机（已登录运行）的微信 4.x 中，按联系人提取语音消息，合并成约 N 秒的音频样本，导出为 WAV / MP3。
图形界面，可在无 Python/Node 的电脑上独立运行。

> 仅用于导出**你本人有权处理**的数据。请遵守当地法律并尊重他人隐私。

## 运行（已打包）

双击 `dist/WxVoiceTool/WxVoiceTool.exe`。

首次启动会：
1. 定位微信数据目录（`xwechat_files`）；
2. 从运行中的微信提取数据库密钥（需微信已登录并保持运行）；
3. 解密数据库并扫描语音；
4. 列出「可提取语音的联系人」，勾选后设置参数导出。

密钥会缓存到 `%LOCALAPPDATA%\WxVoiceTool\key.json`，之后启动跳过提取。
若自动提取失败（微信版本特征变化），会提示手动粘贴 64 位十六进制密钥。

### 自动探测失败时：用【设置】手动指定

顶栏【设置】可手动指定（留空则自动探测，填了无效会自动回退）：

- **微信数据目录**：选 `xwechat_files` 文件夹
- **Weixin.dll**：装到非默认盘/目录时填这个（或直接手动粘贴 key）
- **账号**：多账号时下拉选择

设置保存到 `%LOCALAPPDATA%\WxVoiceTool\config.json`。

## 从源码运行

```
pip install -r requirements.txt
cd runtime && npm install silk-wasm && cd ..
python app.py
```

## 开发

```
python -m pytest -v          # 单元测试
```

结构：`core/`（纯逻辑）、`ui/`（PySide6）、`runtime/`（内置 Node + SILK 解码脚本）。

## 打包

需要标准 CPython（**不要用 Anaconda**：其 Qt/sqlite 的 DLL 在 `Library\bin`，PyInstaller 收不到）。

```
# 1) 准备内置运行时
copy "C:\Program Files\nodejs\node.exe" runtime\node\node.exe
cd runtime && npm install silk-wasm && cd ..
# 2) 构建（用标准 Python 的 venv）
pyinstaller --noconfirm --clean build.spec
# 产物：dist\WxVoiceTool\WxVoiceTool.exe
```

## 说明

- 仅处理 `local_type=34` 语音；排除本人发出的；只导已下载（`voice_data` 存在）的语音。
- 支持累积到目标时长并「裁剪到精确时长」。
- 微信未运行 / 未登录时无法取密钥，会给出明确提示。
