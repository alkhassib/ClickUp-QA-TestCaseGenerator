# ClickUp QA Test-Case Generator

**English** | [العربية](README.ar.md)

A pure-Python script (no n8n) that pulls ready user stories from ClickUp,
generates QA test cases via LangChain + GPT-5 Nano, and creates them back
as new tasks in ClickUp.

## Project structure

```
config.py          Loads settings from .env
models.py          Pydantic schemas (fixed shape for the model output)
prompts/           The three prompts (decoupled from code, easy to edit)
llm_chain.py       The three chains: ambiguity check -> generate -> self review
clickup_client.py  Thin wrapper around ClickUp API v2
pipeline.py        Processes a single user story end to end
main.py            Entry point + periodic polling loop
```

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Copy the settings file**:
   ```bash
   cp .env.example .env
   ```

3. **Fill `.env` with real values**:
   - `CLICKUP_API_TOKEN`: ClickUp -> Settings -> Apps -> Generate
   - `CLICKUP_TEAM_ID`: Workspace ID (from the ClickUp URL or `GET /api/v2/team`)
   - `SOURCE_LIST_ID`: ID of the list holding the user stories
   - `INPUT_COLUMN`: name of the status that triggers the flow (must match ClickUp exactly)
   - `OUTPUT_LIST_ID`: where test-case tasks are created (same as `SOURCE_LIST_ID`, or a different List ID)
   - `OUTPUT_COLUMN`: status applied to the new test-case tasks
   - `STORY_DONE_COLUMN`: status the user story moves to once processed
   - `OPENAI_API_KEY`: your OpenAI key
   - `TEST_CASE_LANGUAGE`: language of the generated test cases — `ar` (Arabic) or `en` (English). Optional, defaults to `ar`

4. **Run once in trial mode** (`DRY_RUN=true` in `.env`):
   ```bash
   python main.py
   ```
   Watch `automation.log` — it prints the names of the test cases that *would*
   be generated, without writing anything to ClickUp.

5. **Once the results look sound**, set `DRY_RUN=false` and run again.

## Choosing the output language

Set `TEST_CASE_LANGUAGE` in `.env` to control the language of the generated
test cases:

```
TEST_CASE_LANGUAGE=en   # English
TEST_CASE_LANGUAGE=ar   # Arabic (default)
```

The setting is case-insensitive (`EN` == `en`) and controls the language of
both the LLM output (titles, steps, expected results) and the labels in each
created ClickUp task's description. Any unsupported value stops the run with a
clear error.

## Reliability note

If an error happens midway through creating the test cases for a story (after
some were created but before it finishes), the script does **not** update the
original story's status, so it is retried on the next cycle — but this means the
test cases that succeeded before the failure may be created again. When this
happens, the log shows exactly which tasks were created before the failure so
you can review/delete them manually. This is a future improvement point (e.g.
adding a custom field on the story that records which test cases were created
so far).

## Local testing

The project was fully checked (syntax + imports + object construction) inside
the development environment, but was **not tested against real ClickUp or
OpenAI calls** because the dev environment has no network access to those
domains. Try it with `DRY_RUN=true` first on your machine to confirm everything
works before relying on it.
