"""
Orchestrates a single processing cycle: fetch the story -> run the chain ->
create the test-case tasks -> update the original story's status.
"""
import logging

from clickup_client import ClickUpClient
from config import Config
from llm_chain import TestCaseChains
from models import TestCase, TestCaseList

logger = logging.getLogger("qa_automation")


# تسميات وصف التكت حسب اللغة المختارة بالإعدادات
_DESCRIPTION_LABELS = {
    "ar": {
        "generated_from": "حالة اختبار مولَّدة تلقائيًا من القصة",
        "type": "النوع",
        "priority": "الأولوية",
        "location": "المكان (النظام / الشاشة)",
        "steps": "الخطوات",
        "test_data": "بيانات الاختبار",
        "expected_result": "النتيجة المتوقعة",
        "notes": "ملاحظات",
    },
    "en": {
        "generated_from": "Test case auto-generated from story",
        "type": "Type",
        "priority": "Priority",
        "location": "Where (system / screen)",
        "steps": "Steps",
        "test_data": "Test data",
        "expected_result": "Expected result",
        "notes": "Notes",
    },
}


def _build_task_description(tc: TestCase, story_title: str, story_url: str, language: str) -> str:
    labels = _DESCRIPTION_LABELS[language]
    steps_text = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(tc.steps))
    test_data_text = "\n".join(f"- {item}" for item in tc.test_data) or "-"
    description = (
        f"{labels['generated_from']}: [{story_title}]({story_url})\n\n"
        f"**{labels['type']}:** {tc.type} | **{labels['priority']}:** {tc.priority}\n\n"
        f"**{labels['location']}:** {tc.location}\n\n"
        f"**{labels['test_data']}:**\n{test_data_text}\n\n"
        f"**{labels['steps']}:**\n{steps_text}\n\n"
        f"**{labels['expected_result']}:** {tc.expected_result}"
    )
    # Gaps and assumptions go last, as a closing section of the ticket
    if tc.notes:
        notes_text = "\n".join(f"- {note}" for note in tc.notes)
        description += f"\n\n---\n**{labels['notes']}:**\n{notes_text}"
    return description


def process_story(
    task: dict,
    chains: TestCaseChains,
    clickup: ClickUpClient,
    config: Config,
) -> None:
    task_id = task["id"]
    story_title = task["name"]
    story_description = (task.get("text_content") or task.get("description") or "").strip()
    story_url = clickup.task_url(task_id)

    logger.info("Starting to process story: %s (%s)", story_title, task_id)

    if not story_description:
        logger.warning("Story %s has no description - skipped", task_id)
        return

    result: TestCaseList = chains.run_full_pipeline(story_description)

    if not result.test_cases:
        logger.warning("No test cases were generated for story %s", task_id)
        return

    if config.dry_run:
        logger.info("[DRY RUN] Instead of creating %d task(s), these are the test-case names that would be generated:", len(result.test_cases))
        for tc in result.test_cases:
            logger.info("  - [%s/%s] %s", tc.type, tc.priority, tc.title)
        return

    created_ids: list[str] = []
    try:
        for tc in result.test_cases:
            description = _build_task_description(tc, story_title, story_url, config.test_case_language)
            created = clickup.create_task(
                list_id=config.output_list_id,
                name=tc.title,
                description=description,
                status=config.output_column,
            )
            created_ids.append(created["id"])
    except Exception:
        # If creation fails midway, we do NOT update the story status so it is
        # retried on the next cycle.
        # Warning: this can duplicate the tasks created before the failure - review them manually.
        logger.exception(
            "Failed to create some test cases for story %s. %d task(s) were created before the failure: %s. "
            "The story status will not be updated - review the tasks manually to avoid duplicates on the next cycle.",
            task_id,
            len(created_ids),
            created_ids,
        )
        return

    clickup.update_task_status(task_id, config.story_done_column)
    logger.info("Finished processing story %s - created %d test case(s)", task_id, len(created_ids))
