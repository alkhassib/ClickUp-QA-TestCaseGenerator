"""
بناء السلاسل الثلاث (فحص الوضوح -> توليد التست كيسز -> مراجعة ذاتية) باستخدام LangChain.
الموديل مثبّت حصراً على GPT-5 Nano عبر إعداد OPENAI_MODEL.
"""
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from models import AmbiguityReview, TestCaseList

PROMPTS_DIR = Path(__file__).parent / "prompts"

# تعليمة اللغة اللي بتتحقن بكل prompt عشان نتحكم بلغة مخرجات الموديل
_LANGUAGE_INSTRUCTIONS = {
    "ar": "اكتب كل المخرجات (العناوين، الخطوات، النتائج المتوقعة) باللغة العربية.",
    "en": "Write all output (titles, steps, expected results) in English.",
}


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


class TestCaseChains:
    """يغلف السلاسل الثلاث ويوفرها كدوال جاهزة للاستخدام"""

    def __init__(self, api_key: str, model: str, language: str = "ar"):
        # ملاحظة: GPT-5 Nano موديل من عائلة الـ reasoning، وما بيدعم تعديل
        # temperature -> بنسيبه على الإعداد الافتراضي عشان نتجنب خطأ بالـ API.
        self._llm = ChatOpenAI(model=model, api_key=api_key)
        self._language_instruction = _LANGUAGE_INSTRUCTIONS[language]

        ambiguity_prompt = ChatPromptTemplate.from_template(_load_prompt("ambiguity_check.txt"))
        generate_prompt = ChatPromptTemplate.from_template(_load_prompt("generate_test_cases.txt"))
        review_prompt = ChatPromptTemplate.from_template(_load_prompt("self_review.txt"))

        self._ambiguity_chain = ambiguity_prompt | self._llm.with_structured_output(AmbiguityReview)
        self._generate_chain = generate_prompt | self._llm.with_structured_output(TestCaseList)
        self._review_chain = review_prompt | self._llm.with_structured_output(TestCaseList)

    def check_ambiguity(self, story: str) -> AmbiguityReview:
        return self._ambiguity_chain.invoke(
            {"story": story, "language_instruction": self._language_instruction}
        )

    def generate_test_cases(self, story: str, gaps: list[str]) -> TestCaseList:
        gaps_text = "\n".join(f"- {g}" for g in gaps) if gaps else "لا يوجد"
        return self._generate_chain.invoke(
            {
                "story": story,
                "gaps": gaps_text,
                "language_instruction": self._language_instruction,
            }
        )

    def self_review(self, story: str, existing: TestCaseList) -> TestCaseList:
        existing_text = "\n".join(f"- {tc.title}" for tc in existing.test_cases) or "لا يوجد"
        return self._review_chain.invoke(
            {
                "story": story,
                "existing_test_cases": existing_text,
                "language_instruction": self._language_instruction,
            }
        )

    def run_full_pipeline(self, story: str) -> TestCaseList:
        """يشغل السلسلة الكاملة ويرجع القائمة النهائية (توليد + مراجعة ذاتية مدموجة)"""
        ambiguity = self.check_ambiguity(story)
        generated = self.generate_test_cases(story, ambiguity.gaps)
        review = self.self_review(story, generated)
        return TestCaseList(test_cases=generated.test_cases + review.test_cases)
