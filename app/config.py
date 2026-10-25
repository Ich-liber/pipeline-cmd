"""配置加载：从 .env 读取 LLM 配置。"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """LLM 与流程配置。"""

    # LLM 底座
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")

    # 流程控制
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "3"))

    @classmethod
    def check(cls) -> None:
        """启动时自检：LLM Key 是否配置。"""
        if not cls.LLM_API_KEY or cls.LLM_API_KEY.startswith("sk-xxx"):
            raise RuntimeError(
                "未配置 LLM_API_KEY。请复制 .env.example 为 .env 并填写 API Key。"
            )


settings = Settings()
