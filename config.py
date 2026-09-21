"""
تحميل الإعدادات من ملف .env والتحقق من وجود كل القيم المطلوبة.
كل قيمة قابلة للتعديل بملف .env بدون أي حاجة نلمس الكود.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get_required(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"الإعداد المطلوب '{key}' غير موجود بملف .env")
    return value


def _get_optional(key: str, default: str) -> str:
    return os.getenv(key, default)


_SUPPORTED_LANGUAGES = ("ar", "en")


def _get_language(key: str, default: str) -> str:
    value = os.getenv(key, default).strip().lower()
    if value not in _SUPPORTED_LANGUAGES:
        raise ValueError(
            f"الإعداد '{key}' لازم يكون واحد من {_SUPPORTED_LANGUAGES}، القيمة الحالية: '{value}'"
        )
    return value


@dataclass(frozen=True)
class Config:
    # ---- ClickUp ----
    clickup_api_token: str
    clickup_team_id: str
    source_list_id: str
    input_column: str
    output_list_id: str
    output_column: str
    story_done_column: str

    # ---- OpenAI ----
    openai_api_key: str
    openai_model: str

    # ---- توليد التست كيسز ----
    # لغة توليد التست كيسز: "ar" عربي أو "en" إنجليزي
    test_case_language: str

    # ---- التشغيل ----
    poll_interval_minutes: int
    max_tasks_per_run: int
    max_retries: int
    dry_run: bool
    log_file_path: str


def load_config() -> Config:
    return Config(
        clickup_api_token=_get_required("CLICKUP_API_TOKEN"),
        clickup_team_id=_get_required("CLICKUP_TEAM_ID"),
        source_list_id=_get_required("SOURCE_LIST_ID"),
        input_column=_get_required("INPUT_COLUMN"),
        output_list_id=_get_required("OUTPUT_LIST_ID"),
        output_column=_get_required("OUTPUT_COLUMN"),
        story_done_column=_get_required("STORY_DONE_COLUMN"),
        openai_api_key=_get_required("OPENAI_API_KEY"),
        openai_model=_get_optional("OPENAI_MODEL", "gpt-5-nano"),
        test_case_language=_get_language("TEST_CASE_LANGUAGE", "ar"),
        poll_interval_minutes=int(_get_optional("POLL_INTERVAL_MINUTES", "10")),
        max_tasks_per_run=int(_get_optional("MAX_TASKS_PER_RUN", "20")),
        max_retries=int(_get_optional("MAX_RETRIES", "3")),
        dry_run=_get_optional("DRY_RUN", "false").strip().lower() == "true",
        log_file_path=_get_optional("LOG_FILE_PATH", "automation.log"),
    )
