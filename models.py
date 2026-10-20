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
    location: str = Field(
        description="مكان تنفيذ الاختبار: اسم النظام أو الوحدة واسم الشاشة (أو مسار الوصول إليها)"
    )
    steps: list[str] = Field(description="خطوات تنفيذ التست بالترتيب")
    test_data: list[str] = Field(
        description=(
            "البيانات المستخدمة في الاختبار: قيم محددة إن أمكن، أو على الأقل نوع البيانات وصيغتها "
            "(مثال: 'البريد الإلكتروني: صيغة صحيحة مثل user@test.com'، 'المبلغ: رقم سالب')"
        )
    )
    expected_result: str = Field(
        description="النتيجة المتوقعة بعد تنفيذ الخطوات، بصيغة محددة قابلة للتحقق (رسالة، أو حالة، أو قيمة تظهر على الشاشة...)"
    )
    notes: list[str] = Field(
        description=(
            "ملاحظات: أي نقص أو غموض في القصة أثّر في هذا الاختبار، وأي افتراض بُني عليه. "
            "تُترك القائمة فارغة إن لم يوجد شيء من ذلك"
        )
    )


class TestCaseList(BaseModel):
    """قائمة تست كيسز"""

    test_cases: list[TestCase] = Field(default_factory=list)
