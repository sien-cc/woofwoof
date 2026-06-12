# 🐙 小爪子 - Claude 桌面宠物

一个基于 PySide6 的可爱章鱼桌面宠物，使用 Claude API 陪伴你聊天、记笔记、看屏幕。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

## ✨ 功能特性

- 🎨 **可爱的章鱼形象**：GIF 和 SVG 动画，多种表情和动作
- 💬 **智能对话**：基于 Claude API，支持扩展思维链
- 📸 **智能截图**：支持白名单窗口截图，自动发送给 Claude 分析
- 📝 **笔记功能**：安全地在 Markdown 文件中记录想法
- 🎯 **首次运行向导**：友好的配置引导，无需手动编辑配置文件
- ⚙️ **完全可配置**：所有 UI 尺寸、动画时长、文本内容都可自定义
- 🌙 **深色模式**：聊天窗口支持亮色/深色主题切换
- 🖼️ **图片上传**：支持拖拽或选择图片发送给 Claude

## 🚀 快速开始

### 首次运行

第一次运行小爪子时，会自动弹出配置向导，引导你：
1. 配置 Claude API Key（支持环境变量）
2. 选择笔记存储路径
3. 自动创建人设和日记模板

只需运行：

```bash
python qt_octopus_pet.py
```

或者双击：

```bat
start.bat
```

### 安装依赖

```bash
pip install -r requirements.txt
```

**可选**：如果需要 SVG 动画预渲染（更流畅的动画效果）：

```bash
playwright install chromium
```

## 📋 配置说明

### API Key 配置

推荐使用环境变量（更安全）：

```powershell
# Windows PowerShell
$env:CLAUDE_API_KEY = “your-api-key-here”

# 或永久设置（系统环境变量）
```

也可以在配置向导中直接输入 API Key（会保存到 `config.json`）。

### 自定义配置

所有配置都在 `config.json` 中，包括：
- UI 尺寸和动画时长（`ui_settings`）
- 截图设置和快捷键
- 聊天记录和上下文设置
- 小爪子的人设和日记路径

参考 `config.example.json` 查看所有可配置项。

## ⌨️ 快捷键配置

小爪子使用 Windows 原生 API 注册全局快捷键，支持键盘和鼠标组合。

### 支持的按键

**键盘**：`f1`-`f12`、`a`-`z`、`0`-`9`  
**鼠标**：`mouse4`（侧键前进）、`mouse5`（侧键后退）  
**修饰键**：`ctrl`、`shift`、`alt`、`win`

### 推荐配置

**游戏玩家**（避免冲突）：
```json
“screenshot_single_hotkey”: “shift+mouse4”,
“screenshot_continuous_hotkey”: “ctrl+mouse4”
```

**普通用户**：
```json
“screenshot_single_hotkey”: “f9”,
“screenshot_continuous_hotkey”: “shift+f9”
```

## 📸 截图白名单

截图功能遵循白名单配置，只截取指定的窗口：

```json
“screenshot_whitelist”: {
  “enabled”: true,
  “prefer”: “foreground”,
  “titles”: [],
  “processes”: [“chrome.exe”, “code.exe”]
}
```

- `prefer: “foreground”`：只截取当前前台窗口（如果在白名单内）
- `processes`：进程名列表（从任务管理器获取，需要 `.exe` 后缀）

## 📝 人设与日记

小爪子会读取人设和日记文件，让对话更有记忆：

- `人设.md`：小爪子的自传和性格设定
- `日记.md`：小爪子最近的经历和心情

首次运行会自动创建模板文件，你可以随时编辑来定制小爪子的性格！

## 🗂️ 文件结构

```
clawwww/
├── qt_octopus_pet.py      # 主程序
├── setup_wizard.py         # 首次运行配置向导
├── pet_core.py            # 核心逻辑（API、截图、笔记）
├── pet_emotions.py        # 表情和动作定义
├── pet_ui.py              # UI 配置（颜色、尺寸）
├── qt_pet_ui.py           # Qt UI 组件
├── config.example.json    # 配置示例
├── templates/             # 人设和日记模板
├── gif/                   # GIF 动画资源
└── svg/                   # SVG 动画资源
```

## 🎨 自定义你的桌面宠物

本项目的架构支持完全自定义，你可以替换成任何角色！

### 替换角色动画

1. **准备你的动画素材**
   - GIF 格式：放在 `gif/` 文件夹
   - SVG 格式：放在 `svg/` 文件夹

2. **命名规则**
   - 文件名需要对应 `pet_emotions.py` 中定义的表情名
   - 例如：`idle.gif`、`happy.gif`、`thinking.gif` 等
   - 或者修改 `pet_emotions.py` 中的 `GIF_EMOTIONS` 和 `SVG_EMOTIONS` 映射

3. **调整配置**
   - 在 `config.json` 中可以修改素材路径：
   ```json
   "assets_path": "gif",
   "svg_assets_path": "svg"
   ```

### 自定义 System Prompt

小爪子的性格和行为由 System Prompt 决定，包括：

1. **人设文件**（`人设.md`）
   - 定义角色的身份、性格、能力
   - 修改这个文件可以让它变成任何角色（猫、狗、机器人...）

2. **日记文件**（`日记.md`）
   - 定义角色最近的"记忆"
   - 让对话更有连贯性

3. **代码中的 Prompt**（`pet_core.py` 的 `build_system_prompt` 方法）
   - 如果需要更深度定制，可以修改这个方法
   - 包括时间感知、工具调用说明等

### 配置文件中的文本

在 `config.json` 的 `ui_settings.text` 中可以修改所有显示文本：

```json
"text": {
  "window_title": "你的宠物名字",
  "pet_name": "宠物昵称",
  "user_name": "主人昵称",
  "input_placeholder": "和宠物说点什么",
  "screenshot_message": "这是主人发送过来的截图。"
}
```

### 实现完全不同的角色

**示例：把小爪子改成猫咪**

1. 替换 `gif/` 和 `svg/` 中的动画为猫咪动画
2. 修改 `人设.md`：
   ```markdown
   # 小猫咪的自传
   
   我是一只可爱的橘猫，喜欢晒太阳和吃小鱼干...
   ```
3. 修改 `config.json` 中的文本：
   ```json
   "window_title": "Meow",
   "pet_name": "小猫咪"
   ```

这样就变成一个猫咪桌面宠物了！🐱

---

## 🎨 表情系统

小爪子有丰富的表情和动作：
- **状态**：idle、thinking、typing、error、notification
- **表情**：happy、question、double_jump、swag
- **工作**：debugger、conducting、juggling、sweeping、building、carrying
- **闲置动作**：idle_doze、idle_yawn、idle_reading、sleeping

Claude 可以通过隐藏代码块选择表情：

````markdown
```pet-emotion
{“emotion”:”happy”}
```
````

## 📦 聊天记录

聊天记录自动保存到 `pet_notes/chat_logs/YYYY-MM-DD.md`。

默认情况下，重启后聊天记录只显示在历史抽屉中，不会自动加载到上下文。

如需重启后恢复上下文，可在 `config.json` 中开启：

```json
“load_today_chat_into_context”: true,
“chat_context_max_messages”: 20
```

## ⚠️ 注意事项

- 截图会将屏幕内容发送给 Claude API，请只将信任的窗口加入白名单
- 首次运行需要配置 API Key，确保有稳定的网络连接
- SVG 动画预渲染需要额外安装 Playwright（可选）

## 🙏 致谢

本项目使用的 SVG 和 GIF 动画资源来自：

- **原项目**：[Clawd Desktop Pet](https://github.com/KebeliSamet0/clawd)
- **原作者**：[KebeliSamet0](https://github.com/KebeliSamet0)
- **License**：MIT License

感谢原作者创作的可爱动画资源！

## 📄 License

本项目基于 MIT License 开源。

- 代码部分：Copyright (c) 2026 sien-cc
- 动画资源：Copyright (c) 2026 KebeliSamet0（原始来源）

详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

如果你觉得小爪子可爱，请给个 ⭐️ Star 吧！

## 💻 开发说明

本项目由 [@sien-cc](https://github.com/sien-cc) 设计和主导开发。

开发过程采用 AI 辅助编程方式，使用 Claude (Anthropic) 和 ChatGPT (OpenAI) 作为代码生成和审核工具。所有功能需求、架构设计和代码审核由人类完成。
