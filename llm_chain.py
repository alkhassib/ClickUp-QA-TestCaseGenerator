"""
بناء السلاسل الثلاث (فحص الوضوح -> توليد التست كيسز -> مراجعة ذاتية) باستخدام LangChain.
الموديل مثبّت حصراً على GPT-5 Nano عبر إعداد OPENAI_MODEL.
"""
import logging
import re
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from models import AmbiguityReview, TestCaseList

PROMPTS_DIR = Path(__file__).parent / "prompts"

logger = logging.getLogger("qa_automation")

# تعليمة اللغة اللي بتتحقن بكل prompt عشان نتحكم بلغة مخرجات الموديل
_LANGUAGE_INSTRUCTIONS = {
    "ar": (
        "اكتب جميع النصوص التي تُخرجها (العناوين، والمكان، والخطوات، وبيانات الاختبار، "
        "والنتائج المتوقعة، والملاحظات، ونقاط الغموض) باللغة العربية الفصحى حصرًا، "
        "حتى لو كانت القصة مكتوبة بلغة أخرى. أبقِ قيم النوع (Positive/Negative/Edge) "
        "والأولوية (High/Medium/Low) كما هي، وكذلك أسماء الحقول والأزرار كما تظهر في النظام."
    ),
    "en": (
        "Write every text you output (titles, location, steps, test data, expected results, "
        "notes, and ambiguity gaps) in English only, even though these instructions and the "
        "story may be written in Arabic. Keep the type (Positive/Negative/Edge) and priority "
        "(High/Medium/Low) values exactly as given."
    ),
}

# Extra reminder appended on the single retry when the output came back in the wrong language
_LANGUAGE_RETRY_REMINDERS = {
    "ar": "تنبيه: الإجابة السابقة لم تكن باللغة العربية الفصحى. أعد كتابة كل شيء بالعربية الفصحى.",
    "en": "Warning: the previous answer was not in English. Rewrite everything in English.",
}

# Placeholder shown to the model when a list (gaps / existing test cases) is empty
_EMPTY_PLACEHOLDERS = {"ar": "لا يوجد", "en": "None"}

_ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")


def _arabic_ratio(texts: list[str]) -> float | None:
    """Share of Arabic letters among Arabic+Latin letters, or None when there is no text."""
    joined = " ".join(texts)
    arabic = len(_ARABIC_LETTER.findall(joined))
    latin = len(_LATIN_LETTER.findall(joined))
    if arabic + latin == 0:
        return None
    return arabic / (arabic + latin)


def _matches_language(texts: list[str], language: str) -> bool:
    ratio = _arabic_ratio(texts)
    if ratio is None:
        return True
    # Arabic output legitimately contains some Latin (CRM, Mendix, field names, emails),
    # and English output may contain an occasional Arabic sample value, hence the margins.
    return ratio >= 0.5 if language == "ar" else ratio <= 0.2


def _output_texts(result: AmbiguityReview | TestCaseList) -> list[str]:
    """Free-text values of a chain result (enum values like type/priority are excluded)."""
    if isinstance(result, AmbiguityReview):
        return list(result.gaps)
    texts: list[str] = []
    for tc in result.test_cases:
        texts += [tc.title, tc.location, tc.expected_result, *tc.steps, *tc.test_data, *tc.notes]
    return texts


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


class TestCaseChains:
    """يغلف السلاسل الثلاث ويوفرها كدوال جاهزة للاستخدام"""

    def __init__(self, api_key: str, model: str, language: str = "ar"):
        # ملاحظة: GPT-5 Nano موديل من عائلة الـ reasoning، وما بيدعم تعديل
        # temperature -> بنسيبه على الإعداد الافتراضي عشان نتجنب خطأ بالـ API.
        self._llm = ChatOpenAI(model=model, api_key=api_key)
        self._language = language
        self._language_instruction = _LANGUAGE_INSTRUCTIONS[language]
        self._empty = _EMPTY_PLACEHOLDERS[language]

        ambiguity_prompt = ChatPromptTemplate.from_template(_load_prompt("ambiguity_check.txt"))
        generate_prompt = ChatPromptTemplate.from_template(_load_prompt("generate_test_cases.txt"))
        review_prompt = ChatPromptTemplate.from_template(_load_prompt("self_review.txt"))

        self._ambiguity_chain = ambiguity_prompt | self._llm.with_structured_output(AmbiguityReview)
        self._generate_chain = generate_prompt | self._llm.with_structured_output(TestCaseList)
        self._review_chain = review_prompt | self._llm.with_structured_output(TestCaseList)

    def _invoke_in_language(self, chain, inputs: dict):
        """Invoke a chain and retry once if the output is not in the configured language."""
        result = chain.invoke({**inputs, "language_instruction": self._language_instruction})
        if _matches_language(_output_texts(result), self._language):
            return result

        logger.warning("Model output was not in '%s' - retrying once with a stronger reminder", self._language)
        reminder = f"{self._language_instruction}\n{_LANGUAGE_RETRY_REMINDERS[self._language]}"
        result = chain.invoke({**inputs, "language_instruction": reminder})
        if not _matches_language(_output_texts(result), self._language):
            logger.warning("Model output is still not in '%s' after the retry - review it manually", self._language)
        return result

    def check_ambiguity(self, story: str) -> AmbiguityReview:
        return self._invoke_in_language(self._ambiguity_chain, {"story": story})

    def generate_test_cases(self, story: str, gaps: list[str]) -> TestCaseList:
        gaps_text = "\n".join(f"- {g}" for g in gaps) if gaps else self._empty
        return self._invoke_in_language(self._generate_chain, {"story": story, "gaps": gaps_text})

    def self_review(self, story: str, existing: TestCaseList, gaps: list[str]) -> TestCaseList:
        existing_text = "\n".join(f"- {tc.title}" for tc in existing.test_cases) or self._empty
        gaps_text = "\n".join(f"- {g}" for g in gaps) if gaps else self._empty
        return self._invoke_in_language(
            self._review_chain,
            {"story": story, "gaps": gaps_text, "existing_test_cases": existing_text},
        )

    def run_full_pipeline(self, story: str) -> TestCaseList:
        """يشغل السلسلة الكاملة ويرجع القائمة النهائية (توليد + مراجعة ذاتية مدموجة)"""
        ambiguity = self.check_ambiguity(story)
        generated = self.generate_test_cases(story, ambiguity.gaps)
        review = self.self_review(story, generated, ambiguity.gaps)
        return TestCaseList(test_cases=generated.test_cases + review.test_cases)
