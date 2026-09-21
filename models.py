"""
مخططات البيانات (Pydantic) اللي بترجعها استدعاءات الموديل.
فرض هاد الشكل الثابت هو اللي بيضمن مخرجات منظمة حتى مع موديل صغير زي GPT-5 Nano.
"""
from typing import Literal

from pydantic import BaseModel, Field


class AmbiguityReview(BaseModel):
    """نتيجة فحص وضوح قصة المستخدم"""

    gaps: list[str] = Field(
        default_factory=list,
        description="لستة نقاط غموض أو نواقص بالقصة. لستة فاضية يعني القصة واضحة",
    )


class TestCase(BaseModel):
    """تست كيس واحد"""

    title: str = Field(description="عنوان مختصر وواضح للتست كيس")
    type: Literal["Positive", "Negative", "Edge"] = Field(description="نوع السيناريو")
    priority: Literal["High", "Medium", "Low"] = Field(description="أولوية التست")
    steps: list[str] = Field(description="خطوات تنفيذ التست بالترتيب")
    expected_result: str = Field(description="النتيجة المتوقعة بعد تنفيذ الخطوات")


class TestCaseList(BaseModel):
    """قائمة تست كيسز"""

    test_cases: list[TestCase] = Field(default_factory=list)
