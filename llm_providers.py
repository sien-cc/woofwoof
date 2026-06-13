"""
LLM Provider 适配器层
支持多套 API 配置，默认使用 OpenAI 兼容格式
特殊格式（Claude 官方、Gemini 官方）通过 format 字段指定
"""

import os
import json
import requests
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime, timedelta


class LLMProvider(ABC):
    """统一的 LLM 提供商接口"""

    def __init__(self, config, api_key, cache_dir=None):
        self.config = config
        self.api_key = api_key
        self.api_base_url = config.get('api_base_url', '')
        self.model = config.get('model', '')
        self.max_tokens = config.get('max_tokens', 4096)
        self.timeout = config.get('timeout', 180)
        self.cache_dir = Path(cache_dir) if cache_dir else None

    @abstractmethod
    def build_content(self, text, image_base64=None):
        """
        构建消息内容（处理文本+图片）
        返回该提供商的消息格式
        """
        pass

    @abstractmethod
    def send_message(self, messages, system_prompt, enable_thinking=False):
        """
        发送消息到 LLM

        Args:
            messages: 对话历史（统一格式）
            system_prompt: 系统提示词
            enable_thinking: 是否启用思维链

        Returns:
            {
                'text': '回复内容',
                'thinking': '思维链内容（如果支持）',
                'metadata': {...}
            }
        """
        pass

    @abstractmethod
    def fetch_models(self):
        """
        从 API 获取可用模型列表

        Returns:
            list: 模型 ID 列表，例如 ['claude-opus-4-6', 'gpt-4']
            None: 如果获取失败或不支持
        """
        pass

    def extract_thinking(self, response):
        """
        尽力从响应中提取思维链，找不到返回 None
        子类可以重写此方法
        """
        return None

    def _load_cache(self, config_id):
        """加载模型缓存（24小时有效）"""
        if not self.cache_dir:
            return None

        cache_file = self.cache_dir / f"model_cache_{config_id}.json"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            timestamp_str = cache_data.get('timestamp')
            if not timestamp_str:
                return None

            timestamp = datetime.fromisoformat(timestamp_str)
            if datetime.now() - timestamp > timedelta(hours=24):
                return None

            return cache_data.get('models')
        except Exception:
            return None

    def _save_cache(self, config_id, models):
        """保存模型缓存"""
        if not self.cache_dir:
            return

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self.cache_dir / f"model_cache_{config_id}.json"

            cache_data = {
                'models': models,
                'timestamp': datetime.now().isoformat()
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容格式（适用于大部分中转 API）"""

    def __init__(self, config, api_key, cache_dir=None):
        super().__init__(config, api_key, cache_dir)
        self.organization = config.get('organization', '')

    def build_content(self, text, image_base64=None):
        """OpenAI 的内容格式"""
        if image_base64:
            return [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": text
                }
            ]
        else:
            return text

    def send_message(self, messages, system_prompt, enable_thinking=False):
        openai_messages = [
            {"role": "system", "content": system_prompt}
        ] + messages

        payload = {
            "model": self.model,
            "messages": openai_messages
        }

        # o1/o3 系列使用 max_completion_tokens
        if 'o1' in self.model.lower() or 'o3' in self.model.lower():
            payload["max_completion_tokens"] = self.max_tokens
        else:
            payload["max_tokens"] = self.max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        if self.organization:
            headers["OpenAI-Organization"] = self.organization

        response = requests.post(
            f"{self.api_base_url}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )

        if response.status_code != 200:
            raise RuntimeError(f"API错误: {response.status_code} - {response.text}")

        result = response.json()
        thinking = self.extract_thinking(result)
        message = result['choices'][0]['message']

        return {
            'text': message['content'],
            'thinking': thinking,
            'metadata': {
                'model': result.get('model'),
                'usage': result.get('usage')
            }
        }

    def extract_thinking(self, response):
        """从 OpenAI 响应中提取推理内容"""
        message = response.get('choices', [{}])[0].get('message', {})
        return message.get('reasoning_content') or message.get('thinking')

    def fetch_models(self):
        """从 OpenAI 兼容 API 获取模型列表"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            if self.organization:
                headers["OpenAI-Organization"] = self.organization

            response = requests.get(
                f"{self.api_base_url}/v1/models",
                headers=headers,
                timeout=10
            )

            if response.status_code != 200:
                return None

            result = response.json()
            models = []

            if 'data' in result:
                for model_data in result['data']:
                    model_id = model_data.get('id') or model_data.get('model')
                    if model_id:
                        models.append(model_id)

            return sorted(models) if models else None

        except Exception:
            return None


class ClaudeOfficialProvider(LLMProvider):
    """Claude 官方 API 格式"""

    def __init__(self, config, api_key, cache_dir=None):
        super().__init__(config, api_key, cache_dir)
        self.enable_thinking = config.get('enable_thinking', False)
        self.thinking_budget_tokens = config.get('thinking_budget_tokens', 10000)

    def build_content(self, text, image_base64=None):
        """Claude 的内容格式：content blocks"""
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

    def send_message(self, messages, system_prompt, enable_thinking=False):
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": messages
        }

        if enable_thinking and self.enable_thinking:
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget_tokens
            }

        response = requests.post(
            f"{self.api_base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json=payload,
            timeout=self.timeout
        )

        if response.status_code != 200:
            raise RuntimeError(f"Claude API错误: {response.status_code} - {response.text}")

        result = response.json()
        thinking = self.extract_thinking(result)

        text_content = None
        for block in result.get('content', []):
            if block.get('type') == 'text':
                text_content = block.get('text', '')
                break

        if text_content is None and len(result.get('content', [])) > 0:
            text_content = result['content'][0].get('text', '')

        return {
            'text': text_content or '',
            'thinking': thinking,
            'metadata': {
                'model': result.get('model'),
                'usage': result.get('usage')
            }
        }

    def extract_thinking(self, response):
        """从 Claude 响应中提取思维链"""
        for block in response.get('content', []):
            if block.get('type') == 'thinking':
                return block.get('thinking', '')
        return None

    def fetch_models(self):
        """从 Claude 官方 API 获取模型列表"""
        try:
            response = requests.get(
                f"{self.api_base_url}/v1/models",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01"
                },
                timeout=10
            )

            if response.status_code != 200:
                return None

            result = response.json()
            models = []

            if 'data' in result:
                for model_data in result['data']:
                    model_id = model_data.get('id') or model_data.get('model')
                    if model_id:
                        models.append(model_id)

            return sorted(models) if models else None

        except Exception:
            return None


class GeminiOfficialProvider(LLMProvider):
    """Google Gemini 官方 API 格式"""

    def build_content(self, text, image_base64=None):
        """Gemini 的内容格式：parts 数组"""
        parts = []
        if image_base64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": image_base64
                }
            })
        parts.append({"text": text})
        return parts

    def send_message(self, messages, system_prompt, enable_thinking=False):
        contents = []

        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"[System Instructions]\n{system_prompt}\n\n[Start of Conversation]"}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I'm ready to assist."}]
            })

        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]

            if isinstance(content, list):
                parts = content
            elif isinstance(content, str):
                parts = [{"text": content}]
            else:
                parts = [{"text": str(content)}]

            contents.append({"role": role, "parts": parts})

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": self.max_tokens
            }
        }

        response = requests.post(
            f"{self.api_base_url}/models/{self.model}:generateContent?key={self.api_key}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout
        )

        if response.status_code != 200:
            raise RuntimeError(f"Gemini API错误: {response.status_code} - {response.text}")

        result = response.json()
        thinking = self.extract_thinking(result)

        text = ""
        if 'candidates' in result and len(result['candidates']) > 0:
            parts = result['candidates'][0]['content']['parts']
            for part in parts:
                if 'text' in part:
                    text += part['text']

        return {
            'text': text,
            'thinking': thinking,
            'metadata': {
                'model': self.model,
                'usage': result.get('usageMetadata')
            }
        }

    def extract_thinking(self, response):
        """从 Gemini 响应中提取思考内容"""
        if 'candidates' in response and len(response['candidates']) > 0:
            parts = response['candidates'][0]['content']['parts']
            for part in parts:
                if 'thought' in part:
                    return part['thought']
        return None

    def fetch_models(self):
        """从 Gemini 官方 API 获取模型列表"""
        try:
            response = requests.get(
                f"{self.api_base_url}/models?key={self.api_key}",
                timeout=10
            )

            if response.status_code != 200:
                return None

            result = response.json()
            models = []

            if 'models' in result:
                for model_data in result['models']:
                    model_name = model_data.get('name', '')
                    if model_name.startswith('models/'):
                        model_id = model_name.replace('models/', '')
                        models.append(model_id)

            return sorted(models) if models else None

        except Exception:
            return None


def create_llm_provider(config, cache_dir=None) -> LLMProvider:
    """
    工厂函数：根据配置创建对应的 LLM 提供商

    Args:
        config: 配置字典，需要包含 'current_config' 和 'api_configs' 字段
        cache_dir: 模型缓存目录（用于缓存模型列表）

    Returns:
        LLMProvider 实例

    Raises:
        ValueError: 配置错误或缺少 API Key
    """
    current_config = config.get('current_config')
    api_configs = config.get('api_configs', {})

    if not current_config or current_config not in api_configs:
        raise ValueError(f"未找到配置 '{current_config}'")

    api_config = api_configs[current_config]

    # 读取 API Key
    api_key = api_config.get('api_key', '').strip()
    if not api_key:
        api_key_env = api_config.get('api_key_env', 'API_KEY')
        api_key = os.getenv(api_key_env, '').strip()

    if not api_key:
        raise ValueError(f"未找到配置 '{current_config}' 的 API Key")

    # 设置超时和 token 限制
    api_config['timeout'] = config.get('api_timeout', 180)
    api_config['max_tokens'] = config.get('api_max_tokens', 4096)

    # 根据 format 选择 Provider
    format_type = api_config.get('format', 'openai').lower()

    if format_type == 'claude':
        return ClaudeOfficialProvider(api_config, api_key, cache_dir)
    elif format_type == 'gemini':
        return GeminiOfficialProvider(api_config, api_key, cache_dir)
    else:
        # 默认使用 OpenAI 兼容格式（适用于大部分中转）
        return OpenAICompatibleProvider(api_config, api_key, cache_dir)


def fetch_models_with_cache(config, cache_dir, config_id=None, force_refresh=False):
    """
    获取模型列表（带缓存）

    Args:
        config: 配置字典
        cache_dir: 缓存目录
        config_id: 配置 ID（如果为 None，使用 current_config）
        force_refresh: 是否强制刷新缓存

    Returns:
        list: 模型列表，失败返回 None
    """
    if config_id is None:
        config_id = config.get('current_config')

    try:
        provider = create_llm_provider(config, cache_dir)

        # 尝试从缓存加载
        if not force_refresh:
            cached_models = provider._load_cache(config_id)
            if cached_models is not None:
                return cached_models

        # 从 API 获取
        models = provider.fetch_models()

        # 保存缓存
        if models:
            provider._save_cache(config_id, models)

        return models

    except Exception:
        return None
