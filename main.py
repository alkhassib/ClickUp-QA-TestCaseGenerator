"""
Entry point - runs a periodic polling cycle at the interval configured in .env.
Run: python main.py
"""
import logging
import sys
import time

from clickup_client import ClickUpClient
from config import Config, load_config
from llm_chain import TestCaseChains
from pipeline import process_story
from single_instance import AlreadyRunningError, SingleInstanceLock


def _setup_logging(log_file_path: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def run_once(config: Config, clickup: ClickUpClient, chains: TestCaseChains) -> None:
    tasks = clickup.get_filtered_tasks(
        team_id=config.clickup_team_id,
        list_id=config.source_list_id,
        status=config.input_column,
    )
    tasks = tasks[: config.max_tasks_per_run]

    if not tasks:
        logging.info("No new tasks in the trigger status (%s)", config.input_column)
        return

    logging.info("Found %d task(s) ready for processing", len(tasks))
    for task in tasks:
        try:
            process_story(task, chains, clickup, config)
        except Exception:
            logging.exception("Unexpected error while processing task %s", task.get("id"))


def _run_loop(config: Config) -> None:
    clickup = ClickUpClient(config.clickup_api_token, max_retries=config.max_retries)
    chains = TestCaseChains(config.openai_api_key, config.openai_model, config.test_case_language)

    logging.info(
        "Starting automation - polling every %d minute(s) (DRY_RUN=%s)",
        config.poll_interval_minutes,
        config.dry_run,
    )

    while True:
        try:
            run_once(config, clickup, chains)
        except Exception:
            logging.exception("Unexpected error in the polling cycle")
        time.sleep(config.poll_interval_minutes * 60)


def main() -> None:
    config = load_config()
    _setup_logging(config.log_file_path)

    # Guard against a second copy running at the same time: two instances would
    # both grab the same story before either updated its status, creating
    # duplicate test cases.
    try:
        with SingleInstanceLock():
            _run_loop(config)
    except AlreadyRunningError as exc:
        logging.error("%s - exiting.", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
