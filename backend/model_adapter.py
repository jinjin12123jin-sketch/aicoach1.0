
import os
from time import perf_counter

class OpenAICompatibleModel:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "")
        self.model = os.getenv("DEEPSEEK_MODEL", "")
        self.last_call = None

    @property
    def configured(self):
        return bool(self.api_key and self.base_url and self.model)

    def chat(
        self,
        messages,
        temperature=0.2,
        max_tokens=1600,
        json_mode=False,
        retries=2,
        thinking=False,
    ):
        if not self.configured:
            raise RuntimeError("请先在 .env 中配置 DeepSeek API。")
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        request = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_body": {
                "thinking": {"type": "enabled" if thinking else "disabled"}
            },
        }
        if json_mode:
            request["response_format"] = {"type": "json_object"}

        started = perf_counter()
        for attempt in range(retries + 1):
            resp = client.chat.completions.create(**request)
            content = resp.choices[0].message.content or ""
            if content.strip():
                usage = getattr(resp, "usage", None)
                self.last_call = {
                    "provider": "openai_compatible",
                    "model": self.model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "json_mode": json_mode,
                    "thinking": thinking,
                    "attempts": attempt + 1,
                    "duration_ms": round((perf_counter() - started) * 1000, 1),
                    "usage": usage.model_dump() if usage and hasattr(usage, "model_dump") else None,
                }
                return content
            if attempt == retries:
                self.last_call = {
                    "provider": "openai_compatible",
                    "model": self.model,
                    "attempts": attempt + 1,
                    "duration_ms": round((perf_counter() - started) * 1000, 1),
                    "error": "empty_content",
                }
                raise RuntimeError(
                    "模型连续返回空内容，请稍后重试。DeepSeek JSON Output 偶尔会出现空响应。"
                )
