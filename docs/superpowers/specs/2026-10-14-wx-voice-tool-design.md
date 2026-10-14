# WxVoiceTool — 微信语音提取器 设计文档

日期：2026-10-14
状态：已确认设计，待实现

## 1. 目标

一个**自包含**的 Windows GUI 工具，从本机（已登录运行）的微信 4.x 中，按联系人提取语音消息，合并成约 N 秒的音频样本，导出为 WAV / MP3。

成功标准：
- 双击 exe（或 app.py）即可运行，界面现代好看。
- 自动定位数据、自动取密钥，无需命令行。
- 列出「有可提取语音的联系人」及其总时长，可单人/多人/全部勾选导出。
- 目标时长、格式（WAV/MP3）、输出目录可配置。
- 打包为可分发 exe（不依赖目标机安装 Python/Node）。

非目标（YAGNI）：
- 不导出文字/图片/视频等其它消息类型。
- 不保留原始 `.silk`。
- 不支持 macOS；不做自动更新；不做多账号同时处理（仅当前登录账号）。

## 2. 背景与已验证事实（原型实测）

- 微信 `Weixin.exe` 版本：4.1.15.13；安装目录 `C:\Program Files\Tencent\Weixin\<版本>\Weixin.exe`。
- 数据根：读取 `%APPDATA%\Tencent\xwechat\config\*.ini` 得 `E:\WX\Documents` → `xwechat_files\<wxid>_<suffix>`。
- 数据库为 SQLCipher 4（WCDB 定制）加密：page 4096、reserve 80（IV 16 + HMAC-SHA512 64）、PBKDF2-HMAC-SHA512 256000 轮、AES-256-CBC、每页 IV 存于页尾 reserve 起始处。
- 密钥 = 内存中 32B「raw」经 `raw XOR staticXorKey` 得到 passphrase（64 hex）。
  - static XOR key：扫描 `Weixin.dll` 中 `48 BA`×4 → `48 85 C0` 特征（4 个 mov rdx,imm64 拼 32B）。
  - raw：扫进程内存匹配结构体特征后读指针指向的 32B（YARA 规则），并用 page1 HMAC-SHA512 校验候选。
- 语音消息：`message_0.db` 中 `Msg_<md5>` 表，`local_type=34`；`message_content` 为 zstd 压缩，解压后形如 `wxid_xxx:\n<msg><voicemsg voicelength="毫秒" voiceformat="4" length="字节" .../></msg>`。
- 发送者：`Msg_.real_sender_id` → 同库 `Name2Id.rowid` → `user_name`（wxid）。
- 语音字节：`media_0.db` 表 `VoiceInfo(chat_name_id, create_time, local_id, svr_id, voice_data BLOB, data_index)`；`svr_id` == 消息 `server_id`。SILK 头为 `\x02#!SILK_V3`。
- 解码：`silk-wasm`（Node）`decode(buf, 24000)` → pcm_s16le。
- 原型结果：90 人有语音，44 人可提取累计 ≥10s。

## 3. 架构

分层，UI 与逻辑解耦（core 不 import PySide6）。

```
wx_voice_tool/
├─ app.py                 入口：QApplication + MainWindow
├─ core/
│  ├─ locate.py           定位数据根/账号目录
│  ├─ keyfinder.py        取密钥（静态+内存+校验），支持缓存与手动 key
│  ├─ dbdecrypt.py        SQLCipher 页解密
│  ├─ voiceindex.py       扫消息库汇总「联系人→语音清单」
│  ├─ voiceexport.py      选段拼接、输出 wav/mp3 编排
│  ├─ silk.py             调 Node 解码 SILK→PCM
│  └─ paths.py            工作目录/缓存/输出默认路径
├─ ui/
│  ├─ main_window.py      主窗口
│  ├─ workers.py          QThread 后台任务 + 信号
│  └─ theme.qss           深色扁平样式
├─ runtime/
│  ├─ node/node.exe       内置 Node 运行时
│  └─ decode_silk.js      SILK→PCM 解码脚本
├─ docs/superpowers/specs/ 本文档
├─ requirements.txt
├─ build.spec             PyInstaller 配置
└─ README.md
```

依赖：`PySide6 pycryptodome zstandard pefile yara-python pymem lameenc`；Node 内置 `silk-wasm`。

## 4. 数据流

1. `locate`：找数据根与账号目录；找不到则提示用户手动选择 `xwechat_files`。
2. `keyfinder`：读缓存 key（`%LOCALAPPDATA%\WxVoiceTool\key.json`，含账号、版本、key）。
   - 缓存缺失或账号/版本变化 → 执行取密钥（需微信运行登录）。
   - 失败 → 提示，并允许用户手动粘贴 64 位 key。
3. `dbdecrypt`：将所需库解密到 `%LOCALAPPDATA%\WxVoiceTool\work\<账号>\`。
4. `voiceindex`：扫 `message_0.db` 汇总，产出 `[(username, name, total_ms, count, clips...)]`，按时长降序。
5. UI 展示，用户勾选 + 设参（时长/格式/输出目录）。
6. `voiceexport`：对每个联系人按时间排序取片段累积到 ≥ 目标时长 → 解码拼接 → 写 WAV 或转 MP3 到输出目录。

## 5. 界面

- 顶栏：账号名 + 状态灯；【重新检测/取密钥】按钮。
- 主区：联系人表格（勾选 / 备注名 / 总时长 / 条数），搜索框，全选/反选。
- 参数区：目标时长（默认 10）、格式 WAV/MP3、输出目录（选择+显示）。
- 底部：进度条 + 可折叠日志。
- 操作：【开始导出】【打开输出目录】【退出】。
- 风格：深色扁平、圆角、主色点缀；长任务显示进度与忙碌态。

## 6. 错误处理

- 微信未运行/未登录 → 明确弹窗与日志。
- 取密钥失败（版本特征变化）→ 提示 + 手动 key 兜底。
- 解密/解析单库异常 → 记录并继续其它库；界面提示。
- 全局异常 → 写 `%LOCALAPPDATA%\WxVoiceTool\logs\`，弹窗。

## 7. 测试 / 验收

- 单元：解密页还原（header 校验）、voicelength 解析、选段累积逻辑、Name2Id 映射。
- 集成（本机真实数据）：联系人清单应含已知 44 人（≥10s）；导出「崔琪 10s WAV」与既有结果音频比对（时长/可听）。
- 多人 + MP3 冒烟。
- 打包后换目录运行，验证内置 Node 解码可用。

## 8. 打包

PyInstaller `onedir`（`--windowed`），附 `runtime/node/`。产物目录含 `WxVoiceTool.exe`。产物大小预计 300–400MB。
