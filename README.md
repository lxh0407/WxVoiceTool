# 微信语音提取器 · WxVoiceTool

从本机（已登录运行）的**微信 PC 4.x** 中，按联系人批量导出语音消息，合并成指定时长的音频样本（WAV / MP3）。
图形界面，可打包为免依赖的独立 exe。

> ## ⚠️ 免责声明
> - 本工具**仅用于导出你本人设备上、且你有权处理**的微信数据（例如个人备份、你自己的账号）。
> - **禁止**用于未经他人同意收集、留存或克隆他人语音，或任何侵犯隐私、诈骗、冒充等违法违规用途。
> - 使用者须自行遵守所在地法律法规及微信服务条款，并对使用后果**自行承担全部责任**；作者及贡献者不对任何直接或间接损害承担责任。
> - 语音内容可能涉及他人隐私，请妥善保管、勿传播。

## 功能
- 自动定位微信数据目录、自动提取数据库密钥（可缓存，二次启动跳过）
- 列出「可提取语音的联系人」及可导出时长，支持搜索 / 多选 / 全选
- 目标时长可调，可选裁剪到精确时长
- 导出 WAV（无损）或 MP3（体积小）
- 自动探测失败时，可在【设置】里手动指定数据目录 / Weixin.dll / 账号，或手动粘贴密钥

## 环境要求
| 项目 | 要求 |
| --- | --- |
| 系统 | Windows 10 / 11 |
| 微信 | PC 版 4.x，需**已登录并保持运行** |
| 运行 exe | 无额外依赖 |
| 源码运行 | Python 3.10+、Node.js 16+ |

## 使用
### 方式一：运行 exe（推荐）
1. 保持微信登录并运行。
2. 双击 `WxVoiceTool.exe`（发行版解压后的文件夹里）。
3. 首次启动会自动取密钥并扫描；勾选联系人 → 设时长/格式/输出目录 →【开始导出】。

### 方式二：从源码运行
```powershell
pip install -r requirements.txt
cd runtime; npm install; cd ..
python app.py
```

## 配置：找不到路径时（重要）
工具会自动探测数据目录与 `Weixin.dll`；**探测失败**时点顶栏【设置】手动指定即可。

### 怎么找「微信数据目录」（xwechat_files）
1. 打开微信 → 左下角 `≡` → 设置 → 文件管理，查看「文件保存位置」；
2. 在该位置下找到 `xwechat_files` 文件夹（内含 `wxid_xxx_xxxx` 子目录，即账号）；
3. 在【设置】的「微信数据目录」里选这个 `xwechat_files` 文件夹。

默认通常在：`C:\Users\<你的用户名>\Documents\xwechat_files`；如改过存储盘，可能在 `D:\`、`E:\` 等。

### 怎么找「Weixin.dll」
1. 右键桌面/开始菜单里的微信图标 → 打开文件所在位置；
2. 进入版本号子目录（例如 `4.1.15.13`），其中就有 `Weixin.dll`；
3. 在【设置】的「Weixin.dll」里选它。

默认通常在：`C:\Program Files\Tencent\Weixin\<版本号>\Weixin.dll`；装到别的盘就填对应路径。
（也可以跳过 dll，直接手动粘贴 64 位十六进制密钥。）

### 配置文件位置
- 设置：`%LOCALAPPDATA%\WxVoiceTool\config.json`
- 密钥缓存：`%LOCALAPPDATA%\WxVoiceTool\key.json`

## 打包（独立 exe）
需使用**标准 CPython**（**不要用 Anaconda**：其 Qt/sqlite 的 DLL 在 `Library\bin`，PyInstaller 收不到，会导致 `Shiboken / _sqlite3` 加载失败）。

```powershell
pip install -r requirements.txt
cd runtime; npm install; cd ..
mkdir runtime\node
copy "C:\Program Files\nodejs\node.exe" runtime\node\node.exe
pip install pyinstaller
pyinstaller --noconfirm --clean build.spec
# 产物：dist\WxVoiceTool\WxVoiceTool.exe（整个文件夹可拷到无 Python/Node 的电脑运行）
```

## 项目结构
```
app.py            入口
core/             纯逻辑：定位 / 取密钥 / 解密 / 索引 / 导出
ui/               PySide6 界面（主窗口、设置、后台线程、样式）
runtime/          内置 Node 解码脚本 decode_silk.js（依赖 silk-wasm）
tests/            单元测试
build.spec        PyInstaller 配置
```

## 测试
```powershell
python -m pytest -v
```

## 原理（简述）
微信 PC 4.x 的本地库为 SQLCipher 加密。本工具从正在运行的微信进程内存中恢复账号密钥（静态特征 + 内存扫描 + 页 HMAC 校验），解密所需数据库后解析语音消息，并用 SILK 解码器转为 PCM 输出。

## License
[MIT](LICENSE)
