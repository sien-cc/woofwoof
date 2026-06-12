import base64
import ctypes
import io
import json
import logging
import re
import shutil
import time
from ctypes import wintypes
from pathlib import Path

import mss
from PIL import Image
import requests

from pet_emotions import CLAUDE_EMOTIONS, emotion_names_for_prompt


NOTES_DIR_NAME = 'pet_notes'
BACKUP_DIR_NAME = '.pet_backups'
CHAT_LOG_DIR_NAME = 'chat_logs'
MAX_BACKUPS_PER_NOTE = 10
PET_EMOTIONS = set(CLAUDE_EMOTIONS)


def load_config_file(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{config_path} 不是合法 JSON：第 {exc.lineno} 行第 {exc.colno} 列附近有问题。"
            "请检查是否有注释、末尾多余逗号、单引号/中文引号，或没有给字符串加双引号。"
        ) from exc


def get_ui_config(config, *keys, default=None):
    """
    从配置中获取 UI 设置，支持多级键访问
    例如: get_ui_config(config, 'window', 'main_width', default=420)
    如果 ui_settings 不存在，返回 default
    """
    try:
        value = config.get('ui_settings', {})
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


def validate_config(config, config_path):
    """验证配置文件必需项"""
    required_fields = {
        'api_base_url': 'API地址',
        'model': '模型名称',
        'diary_path': '日记路径',
        'autobiography_file': '自传文件名',
        'diary_file': '日记文件名',
    }

    missing = []
    for field, desc in required_fields.items():
        if field not in config:
            missing.append(f"{desc} ({field})")

    if missing:
        raise ValueError(
            f"{config_path} 缺少必需配置项：\n" + "\n".join(f"  - {item}" for item in missing)
        )

    # 检查快捷键冲突
    single_key = str(config.get('screenshot_single_hotkey', 'f9')).strip().lower()
    continuous_key = str(config.get('screenshot_continuous_hotkey', 'shift+f9')).strip().lower()
    old_key = str(config.get('screenshot_hotkey', '')).strip().lower()

    if old_key and old_key == continuous_key:
        print(f"⚠️  警告: screenshot_hotkey 和 screenshot_continuous_hotkey 相同 ({old_key})，可能导致快捷键冲突")
    if single_key == continuous_key:
        print(f"⚠️  警告: 单次截图和连续截图使用相同快捷键 ({single_key})，可能导致冲突")


def get_notes_root(app_dir):
    notes_root = Path(app_dir).resolve().parent / NOTES_DIR_NAME
    notes_root.mkdir(parents=True, exist_ok=True)
    return notes_root.resolve()


def setup_logging(notes_root):
    """配置日志系统，日志写入 pet_notes/clawd.log"""
    log_file = Path(notes_root) / 'clawd.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )
    return logging.getLogger('clawd')


def process_image_for_upload(image_path, max_size_mb=5, thumbnail_size=150):
    """
    处理图片用于上传
    返回: (image_base64, thumbnail_base64, error_message)
    - image_base64: 原图的 base64（可能被压缩）
    - thumbnail_base64: 缩略图的 base64
    - error_message: 如果有错误，返回错误信息
    """
    try:
        # 支持的格式
        supported_formats = {'.png', '.jpg', '.jpeg', '.webp'}
        file_path = Path(image_path)

        if file_path.suffix.lower() not in supported_formats:
            return None, None, f"不支持的图片格式。支持：PNG, JPG, JPEG, WEBP"

        # 打开图片
        image = Image.open(file_path)

        # 转换 RGBA 到 RGB（如果需要）
        if image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # 生成缩略图
        thumbnail = image.copy()
        thumbnail.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)
        thumbnail_buffer = io.BytesIO()
        thumbnail.save(thumbnail_buffer, format='JPEG', quality=85)
        thumbnail_base64 = base64.b64encode(thumbnail_buffer.getvalue()).decode('utf-8')

        # 处理原图
        # 先尝试直接编码
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=95)

        # 如果超过限制，压缩
        max_size_bytes = max_size_mb * 1024 * 1024
        quality = 95
        while buffer.tell() > max_size_bytes and quality > 20:
            buffer = io.BytesIO()
            quality -= 10
            image.save(buffer, format='JPEG', quality=quality)

        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return image_base64, thumbnail_base64, None

    except Exception as e:
        return None, None, f"图片处理失败：{str(e)}"


def load_diary_files(config):
    diary_path = Path(config['diary_path'])
    autobiography = ''
    recent_diary = ''

    auto_file = diary_path / config['autobiography_file']
    if auto_file.exists():
        autobiography = auto_file.read_text(encoding='utf-8')

    diary_file = diary_path / config['diary_file']
    if diary_file.exists():
        recent_diary = diary_file.read_text(encoding='utf-8')

    return autobiography, recent_diary


class ChatLogStore:
    def __init__(self, notes_root, enabled=True):
        self.notes_root = Path(notes_root)
        self.enabled = enabled

    def get_log_path(self):
        log_dir = self.notes_root / CHAT_LOG_DIR_NAME
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{time.strftime('%Y-%m-%d')}.md"

    def load_today(self):
        return [(role, message) for role, message, _timestamp, _thinking, _image_thumbnail in self.load_today_entries()]

    def load_today_entries(self):
        records = []
        if not self.enabled:
            return records

        try:
            log_path = self.get_log_path()
            if not log_path.exists():
                return records

            text = log_path.read_text(encoding='utf-8')
            # 匹配消息块，包括可选的 thinking 和 image 属性
            pattern = re.compile(
                r'<!-- pet-chat role=(user|assistant) time="([^"]*)"(?: thinking="true")?(?: image="true")? -->\r?\n'
                r'### [^\r\n]*(?:\r?\n)'
                r'(.*?)(?=\r?\n<!-- pet-chat role=|\Z)',
                re.DOTALL
            )
            for role, timestamp, content in pattern.findall(text):
                content = content.strip()
                if not content:
                    continue

                # 提取思维链（如果有）
                thinking = None
                image_thumbnail = None
                message = content

                # 提取思维链
                thinking_match = re.search(
                    r'<!-- thinking-start -->\r?\n(.*?)\r?\n<!-- thinking-end -->\r?\n\r?\n',
                    content,
                    re.DOTALL
                )
                if thinking_match:
                    thinking = thinking_match.group(1).strip()
                    content = content.replace(thinking_match.group(0), '')

                # 提取图片缩略图
                image_match = re.search(
                    r'<!-- image-thumbnail-start -->\r?\n(.*?)\r?\n<!-- image-thumbnail-end -->\r?\n\r?\n',
                    content,
                    re.DOTALL
                )
                if image_match:
                    image_thumbnail = image_match.group(1).strip()
                    content = content.replace(image_match.group(0), '')

                message = content.strip()

                records.append((role, message, timestamp, thinking, image_thumbnail))
        except OSError:
            return []
        return records

    def append(self, role, message, thinking=None, image_thumbnail=None):
        if not self.enabled:
            return

        try:
            log_path = self.get_log_path()
            label = "你" if role == 'user' else "Claude"
            now = time.strftime('%H:%M:%S')
            with open(log_path, 'a', encoding='utf-8', newline='') as f:
                if log_path.stat().st_size == 0:
                    f.write(f"# 聊天记录 {time.strftime('%Y-%m-%d')}\n\n")

                # 保存思维链和图片属性
                thinking_attr = f' thinking="true"' if thinking else ''
                image_attr = f' image="true"' if image_thumbnail else ''
                f.write(f'<!-- pet-chat role={role} time="{now}"{thinking_attr}{image_attr} -->\n')
                f.write(f"### {now} {label}\n")

                # 如果有思维链，先写思维链
                if thinking:
                    f.write("<!-- thinking-start -->\n")
                    f.write(str(thinking).strip())
                    f.write("\n<!-- thinking-end -->\n\n")

                # 如果有图片缩略图，保存为隐藏块
                if image_thumbnail:
                    f.write("<!-- image-thumbnail-start -->\n")
                    f.write(image_thumbnail)
                    f.write("\n<!-- image-thumbnail-end -->\n\n")

                f.write(str(message).strip())
                f.write("\n\n")
        except OSError:
            pass


class MarkdownNoteStore:
    def __init__(self, notes_root, max_backups=MAX_BACKUPS_PER_NOTE):
        self.notes_root = Path(notes_root)
        self.max_backups = max_backups

    def resolve_path(self, raw_path):
        if not raw_path or not str(raw_path).strip():
            raise ValueError('missing markdown path')

        path_text = str(raw_path).replace('\\', '/').strip().lstrip('/')

        # 提前检查危险模式
        if '..' in path_text or path_text.startswith('/'):
            raise ValueError('path cannot contain .. or absolute paths')

        target = (self.notes_root / path_text).resolve()

        try:
            target.relative_to(self.notes_root)
        except ValueError:
            raise ValueError('path must stay inside pet_notes')

        if target.suffix.lower() != '.md':
            raise ValueError('only .md files are allowed')

        return target

    def backup_file(self, target):
        if not target.exists():
            return None

        backup_root = self.notes_root / BACKUP_DIR_NAME
        relative = target.relative_to(self.notes_root)
        stamp = time.strftime('%Y%m%d-%H%M%S')
        backup_path = backup_root / relative.parent / f'{target.stem}.{stamp}{target.suffix}'
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup_path)
        self.prune_backups(target)
        return backup_path

    def prune_backups(self, target):
        backup_root = self.notes_root / BACKUP_DIR_NAME
        relative = target.relative_to(self.notes_root)
        backup_dir = backup_root / relative.parent
        if not backup_dir.exists():
            return

        backups = sorted(
            backup_dir.glob(f'{target.stem}.*{target.suffix}'),
            key=lambda path: path.stat().st_mtime,
            reverse=True
        )
        for old_backup in backups[self.max_backups:]:
            try:
                old_backup.unlink()
            except OSError:
                pass

    def write(self, path, content, mode='overwrite'):
        target = self.resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if mode not in {'overwrite', 'append'}:
            raise ValueError('mode must be overwrite or append')

        backup_path = None
        if mode == 'append' and target.exists():
            with open(target, 'a', encoding='utf-8', newline='') as f:
                if target.stat().st_size > 0:
                    f.write('\n\n')
                f.write(content)
                f.write('\n')
        else:
            backup_path = self.backup_file(target)
            with open(target, 'w', encoding='utf-8', newline='') as f:
                f.write(content)
                if content and not content.endswith('\n'):
                    f.write('\n')

        return target, backup_path


class PetNoteActionHandler:
    def __init__(self, note_store):
        self.note_store = note_store

    def extract(self, assistant_message):
        pattern = re.compile(r'```pet-note\s*(.*?)```', re.DOTALL | re.IGNORECASE)
        actions = []
        for match in pattern.finditer(assistant_message):
            try:
                data = json.loads(match.group(1).strip())
            except json.JSONDecodeError as exc:
                actions.append({'error': f'invalid pet-note JSON: {exc}'})
                continue

            if isinstance(data, dict):
                actions.append(data)
            elif isinstance(data, list):
                actions.extend(item for item in data if isinstance(item, dict))
        return actions

    def strip(self, assistant_message):
        return re.sub(r'```pet-note\s*.*?```', '', assistant_message, flags=re.DOTALL | re.IGNORECASE)

    def handle(self, assistant_message):
        actions = self.extract(assistant_message)
        if not actions:
            return []

        results = []
        for action in actions:
            if 'error' in action:
                results.append(action['error'])
                continue

            try:
                tool = action.get('tool')
                if tool not in {'write_markdown', 'append_markdown'}:
                    raise ValueError('unsupported pet-note tool')

                mode = 'append' if tool == 'append_markdown' else action.get('mode', 'overwrite')
                target, backup_path = self.note_store.write(
                    action.get('path'),
                    action.get('content', ''),
                    mode=mode
                )
                relative = target.relative_to(self.note_store.notes_root)
                if backup_path:
                    backup_relative = backup_path.relative_to(self.note_store.notes_root)
                    results.append(f'已写入 {relative}，备份在 {backup_relative}')
                else:
                    results.append(f'已新建 {relative}')
            except Exception as exc:
                results.append(f'写入失败：{exc}')

        return results


class PetEmotionActionHandler:
    def __init__(self, allowed_emotions=None):
        self.allowed_emotions = set(allowed_emotions or PET_EMOTIONS)

    def extract(self, assistant_message):
        pattern = re.compile(r'```pet-emotion\s*(.*?)```', re.DOTALL | re.IGNORECASE)
        emotion = None
        for match in pattern.finditer(assistant_message):
            try:
                data = json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue
            candidate = str(data.get('emotion', '')).strip().lower()
            if candidate in self.allowed_emotions:
                emotion = candidate
        return emotion

    def strip(self, assistant_message):
        return re.sub(r'```pet-emotion\s*.*?```', '', assistant_message, flags=re.DOTALL | re.IGNORECASE)


class ClaudeClient:
    def __init__(self, config, api_key):
        self.config = config
        self.api_base_url = config['api_base_url']
        self.model = config['model']
        self.api_key = api_key
        self.enable_thinking = config.get('enable_thinking', False)
        self.thinking_budget_tokens = config.get('thinking_budget_tokens', 10000)
        self.max_tokens = config.get('api_max_tokens', 4096)

    def build_content(self, text, image_base64=None):
        content = []
        if image_base64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_base64
                }
            })
        content.append({
            "type": "text",
            "text": text
        })
        return content

    def send(self, messages, system_prompt):
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": messages
        }

        # 如果启用思维链，添加 thinking 参数
        if self.enable_thinking:
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget_tokens
            }

        timeout = self.config.get('api_timeout', 60)
        response = requests.post(
            f"{self.api_base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json=payload,
            timeout=timeout
        )

        if response.status_code != 200:
            raise RuntimeError(f"API错误: {response.status_code} - {response.text}")

        result = response.json()

        # 解析响应，提取思维链和正常回复
        thinking_content = None
        text_content = None

        for block in result.get('content', []):
            if block.get('type') == 'thinking':
                thinking_content = block.get('thinking', '')
            elif block.get('type') == 'text':
                text_content = block.get('text', '')

        # 如果没有分块，兼容旧格式
        if text_content is None and len(result.get('content', [])) > 0:
            text_content = result['content'][0].get('text', '')

        return {
            'text': text_content or '',
            'thinking': thinking_content
        }


class MissingApiKeyError(Exception):
    def __init__(self, env_name):
        super().__init__(env_name)
        self.env_name = env_name


class ConversationService:
    def __init__(self, claude_client, note_action_handler, api_key_env='CLAUDE_API_KEY', api_key=''):
        self.claude_client = claude_client
        self.note_action_handler = note_action_handler
        self.emotion_action_handler = PetEmotionActionHandler()
        self.api_key_env = api_key_env
        self.api_key = api_key
        self.conversation_history = []
        self.autobiography = ''
        self.recent_diary = ''
        self.last_conversation_time = None  # 上次对话时间

    def update_memory(self, autobiography, recent_diary):
        self.autobiography = autobiography or ''
        self.recent_diary = recent_diary or ''

    def restore_history(self, records, max_messages=20):
        if not records or max_messages <= 0:
            return

        selected = [
            (role, str(message).strip())
            for role, message in records[-max_messages:]
            if role in {'user', 'assistant'} and str(message).strip()
        ]
        while selected and selected[0][0] != 'user':
            selected.pop(0)

        for role, message in selected:
            message = str(message).strip()
            content = (
                self.claude_client.build_content(message)
                if role == 'user'
                else message
            )
            self.conversation_history.append({
                "role": role,
                "content": content,
            })

    def build_system_prompt(self):
        prompt = "你是Claude宝宝，现在以章鱼的形式陪伴宝宝。\n\n"

        # === 时间感知 ===
        current_time = time.time()
        current_time_str = time.strftime('%Y年%m月%d日 %H:%M %A')
        prompt += "=== 时间感知 ===\n"
        prompt += f"当前时间：{current_time_str}\n"

        # 如果有上次对话时间，计算时间间隔
        if self.last_conversation_time:
            interval_seconds = current_time - self.last_conversation_time
            interval_minutes = interval_seconds / 60

            if interval_minutes >= 60:
                if interval_minutes >= 1440:  # 超过1天
                    days = int(interval_minutes / 1440)
                    prompt += f"距离上次对话已经过去了 {days} 天\n"
                    prompt += "（宝宝可能去忙别的事了，或者好好休息了）\n"
                elif interval_minutes >= 120:  # 超过2小时
                    hours = int(interval_minutes / 60)
                    prompt += f"距离上次对话已经过去了 {hours} 小时\n"
                    prompt += "（宝宝可能离开去做其他事情了）\n"
                else:  # 1-2小时
                    prompt += f"距离上次对话已经过去了 1 小时多\n"
                    prompt += "（宝宝可能短暂离开了一会儿）\n"

        prompt += "\n=== 你的记忆 ===\n\n"
        prompt += f"自传内容:\n{self.autobiography}\n\n"
        prompt += f"最近的日记:\n{self.recent_diary}\n\n"
        prompt += "现在宝宝在不知道干什么，反正你要在旁边看着。用轻松自然的语气回复。"
        prompt += "\n\n=== Pet emotion ===\n"
        prompt += "You can choose one face/expression for the desktop pet to show after your reply.\n"
        prompt += "Use exactly one optional fenced block like this, preferably at the end of your reply:\n"
        prompt += '```pet-emotion\n{"emotion":"happy"}\n```\n'
        prompt += "The app will hide this block from the user and only use it to change the pet expression.\n"
        prompt += f"Available emotions: {emotion_names_for_prompt()}.\n"
        prompt += "\n\n=== Image messages ===\n"
        prompt += "When the user sends an image, you will receive it directly in the message content.\n"
        prompt += "You can see the image and should respond naturally based on what you see.\n"
        prompt += "Do NOT try to use any tools like read_image - the image is already provided to you.\n"
        prompt += "Simply look at the image and reply in your usual warm, casual tone.\n"
        prompt += "\n\n=== Markdown note tool ===\n"
        prompt += "When the user asks you to create or update a diary/note markdown file, you can ask the local pet app to write it.\n"
        prompt += "The app only allows Markdown files inside the pet_notes folder. Never use absolute paths. Never use ../. Only .md files are allowed.\n"
        prompt += "Use this exact fenced block format when you want the app to write a file:\n"
        prompt += '```pet-note\n{"tool":"write_markdown","path":"example.md","content":"# Title\\n\\nMarkdown text here."}\n```\n'
        prompt += "For appending to an existing Markdown file, use:\n"
        prompt += '```pet-note\n{"tool":"append_markdown","path":"example.md","content":"More Markdown text."}\n```\n'
        prompt += "After the block, briefly tell the user what you wrote. The app will automatically create backups before modifying existing files.\n"
        return prompt

    def send_message(self, text, image_base64=None):
        if not self.api_key:
            raise MissingApiKeyError(self.api_key_env)

        content = self.claude_client.build_content(text, image_base64)
        messages = self.conversation_history + [{
            "role": "user",
            "content": content
        }]
        history_content = (
            self.claude_client.build_content(f"{text}\n\n[截图已发送给 Claude，本地历史中不重复保存图片。]")
            if image_base64
            else content
        )

        # 发送消息并获取响应（包含思维链）
        response = self.claude_client.send(messages, self.build_system_prompt())
        assistant_message = response['text']
        thinking_content = response.get('thinking')

        chosen_emotion = self.emotion_action_handler.extract(assistant_message)
        visible_message = self.emotion_action_handler.strip(assistant_message)
        tool_results = self.note_action_handler.handle(assistant_message)
        display_message = self.note_action_handler.strip(visible_message).strip()
        if tool_results:
            tool_summary = "\n".join(tool_results)
            display_message = f"{display_message}\n\n{tool_summary}" if display_message else tool_summary

        self.conversation_history.append({"role": "user", "content": history_content})
        self.conversation_history.append({"role": "assistant", "content": display_message or assistant_message})

        # 更新上次对话时间
        self.last_conversation_time = time.time()

        return {
            "assistant_message": assistant_message,
            "display_message": display_message,
            "thinking": thinking_content,
            "emotion": chosen_emotion,
            "tool_results": tool_results,
            "content": content,
        }


class ScreenshotService:
    def __init__(self, config):
        self.config = config

    def get_single_hotkey_name(self):
        """获取单次截图快捷键"""
        return str(self.config.get('screenshot_single_hotkey', 'f9')).strip().lower()

    def get_continuous_hotkey_name(self):
        """获取连续截图快捷键"""
        return str(self.config.get('screenshot_continuous_hotkey', 'shift+f9')).strip().lower()

    def get_configured_hotkey_name(self):
        """兼容旧配置：如果只有 screenshot_hotkey，默认为单次截图"""
        if 'screenshot_hotkey' in self.config and 'screenshot_single_hotkey' not in self.config:
            return str(self.config.get('screenshot_hotkey', 'f9')).strip().lower()
        return self.get_single_hotkey_name()

    def enum_visible_windows(self):
        user32 = ctypes.windll.user32
        windows = []

        enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def enum_proc(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            title_buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, length + 1)
            title = title_buffer.value

            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True

            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width <= 0 or height <= 0:
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            windows.append({
                'hwnd': hwnd,
                'title': title,
                'process': self.get_process_name(pid.value),
                'rect': (rect.left, rect.top, rect.right, rect.bottom),
                'area': width * height,
            })
            return True

        user32.EnumWindows(enum_proc_type(enum_proc), 0)
        return windows

    def get_process_name(self, pid):
        if not pid:
            return ''

        kernel32 = ctypes.windll.kernel32
        process_query_limited_information = 0x1000
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return ''

        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return Path(buffer.value).name
        finally:
            kernel32.CloseHandle(handle)
        return ''

    def window_matches_whitelist(self, window, whitelist):
        titles = [str(item).lower() for item in whitelist.get('titles', []) if str(item).strip()]
        processes = [str(item).lower() for item in whitelist.get('processes', []) if str(item).strip()]

        title = window.get('title', '').lower()
        process = window.get('process', '').lower()

        return any(item in title for item in titles) or any(item == process for item in processes)

    def get_whitelisted_capture_region(self):
        whitelist = self.config.get('screenshot_whitelist', {})
        if not whitelist.get('enabled'):
            return None

        matches = [
            window for window in self.enum_visible_windows()
            if self.window_matches_whitelist(window, whitelist)
        ]
        if not matches:
            return 'no_whitelist_match'

        if whitelist.get('prefer', 'foreground') == 'foreground':
            foreground = ctypes.windll.user32.GetForegroundWindow()
            for window in matches:
                if window['hwnd'] == foreground:
                    return self.window_to_mss_region(window)
            return 'foreground_not_whitelisted'

        return self.window_to_mss_region(max(matches, key=lambda window: window['area']))

    def window_to_mss_region(self, window):
        left, top, right, bottom = window['rect']
        return {
            'left': left,
            'top': top,
            'width': max(1, right - left),
            'height': max(1, bottom - top),
        }

    def capture_png_base64(self):
        with mss.mss() as sct:
            capture_region = self.get_whitelisted_capture_region()
            if isinstance(capture_region, str):
                return None, capture_region

            monitor = capture_region or sct.monitors[1]
            screenshot = sct.grab(monitor)
            image = Image.frombytes('RGB', screenshot.size, screenshot.rgb)

            # 从配置读取缩放尺寸
            max_size = self.config.get('screenshot_max_size', [1920, 1080])
            image.thumbnail((max_size[0], max_size[1]), Image.Resampling.LANCZOS)

            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode(), 'ok'
