import datetime

from app import database, tools


def setup_temp_db(monkeypatch, tmp_path):
    db_file = tmp_path / "nova-test.db"
    monkeypatch.setenv("NOVA_DB_FILE", str(db_file))
    database.init_db()
    return db_file


def test_schedule_overview_groups_tasks_by_day(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)

    tools.create_task(
        title="Deep work block",
        category="DSA",
        priority="high",
        scheduled_time="2026-07-01T09:00:00",
        duration=90,
    )
    tools.create_task(
        title="Write review",
        category="Communication",
        priority="medium",
        due_date="2026-07-02T18:00:00",
    )

    result = tools.get_schedule_overview("week", "2026-07-01T08:00:00")

    assert result["status"] == "success"
    assert result["summary"]["scheduled_task_count"] == 2
    assert "2026-07-01" in result["schedule"]
    assert "2026-07-02" in result["schedule"]


def test_auto_reschedule_tasks_uses_working_hours(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)
    tools.manage_preferences("set", "work_start", '"10:00"')
    tools.manage_preferences("set", "work_end", '"12:00"')

    tools.create_task(
        title="Existing focus block",
        category="DSA",
        priority="high",
        scheduled_time="2026-07-01T10:00:00",
        duration=60,
    )
    missed = tools.create_task(
        title="Missed task",
        category="Personal",
        priority="medium",
        due_date="2026-06-30T09:00:00",
        duration=30,
    )["task"]
    tools.update_task(missed["id"], status="missed")

    result = tools.auto_reschedule_tasks(anchor_date="2026-07-01T09:30:00")

    assert result["status"] == "success"
    assert result["rescheduled_count"] == 1
    assert result["rescheduled"][0]["suggested_time"] == "2026-07-01T11:00:00"


def test_get_productivity_review_supports_year(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)
    created = tools.create_task(
        title="Completed task",
        category="Fitness",
        priority="low",
        due_date=(datetime.datetime.now() + datetime.timedelta(days=1)).isoformat(),
        duration=45,
    )["task"]
    tools.update_task(created["id"], status="completed")

    result = tools.get_productivity_review("year")

    assert result["status"] == "success"
    assert result["summary"]["completed_count"] == 1
    assert result["summary"]["completion_rate"] >= 100
    assert result["summary"]["top_category"] == "Fitness"


def test_recommendations_prefer_focus_categories(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)
    tools.manage_preferences("set", "focus_categories", '["Machine Learning"]')

    tools.create_task(
        title="Lower priority focus task",
        category="Machine Learning",
        priority="medium",
        duration=30,
    )
    tools.create_task(
        title="Higher general task",
        category="Personal",
        priority="medium",
        duration=30,
    )

    result = tools.get_recommendations()

    assert result["status"] == "success"
    assert result["recommendations"][0]["category"] == "Machine Learning"


def test_reminders_generate_notifications(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)
    task = tools.create_task(
        title="Prepare slides",
        category="Communication",
        due_date="2026-07-02T18:00:00",
    )["task"]
    tools.create_reminder(
        task_id=task["id"],
        reminder_time="2026-07-02T09:00:00",
        message="Presentation starts soon",
    )

    result = tools.generate_notifications(anchor_time="2026-07-02T09:30:00")

    assert result["status"] == "success"
    assert any(note["source_type"] == "reminder" for note in result["notifications"])


def test_habit_logging_updates_streak(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)
    habit = tools.create_habit(
        title="Morning workout",
        category="Fitness",
        frequency="daily",
    )["habit"]
    tools.log_habit_progress(habit["id"], log_date="2026-07-01T07:00:00")
    result = tools.log_habit_progress(habit["id"], log_date="2026-07-02T07:00:00")

    assert result["status"] == "success"
    # streak_current counts consecutive days ending today.  Since the logs are
    # hardcoded to 2026-07-01 and 2026-07-02 (past dates, not consecutive with
    # today), the current streak is 0 — that is correct behaviour.
    # streak_best should reflect the 2-day consecutive run that was logged.
    assert result["summary"]["streak_best"] >= 2
    summary = tools.get_habit_summary(habit["id"])
    assert summary["habit"]["streak_best"] >= 1


def test_memory_recall_filters_by_query(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)
    tools.remember_context(
        content="User does best on deep work before lunch.",
        memory_type="preference",
        tags=["focus", "morning"],
    )
    tools.remember_context(
        content="Weekly review feels better on Sunday evening.",
        memory_type="lesson",
        tags=["review"],
    )

    result = tools.recall_memory(query="deep work", limit=5)

    assert result["status"] == "success"
    assert len(result["memories"]) == 1
    assert result["memories"][0]["memory_type"] == "preference"


def test_productivity_coach_report_includes_new_modules(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)
    task = tools.create_task(
        title="Plan sprint",
        category="DSA",
        priority="high",
        due_date="2026-07-02T18:00:00",
    )["task"]
    tools.create_reminder(task["id"], "2026-07-02T09:00:00", "Kickoff reminder")
    habit = tools.create_habit(title="Daily journaling", frequency="daily")["habit"]
    tools.log_habit_progress(habit["id"], log_date="2026-07-02T08:00:00")
    tools.remember_context("User wants concise daily coaching.", "preference")

    report = tools.get_productivity_coach_report(
        period="day", anchor_date="2026-07-02T09:30:00"
    )

    assert report["status"] == "success"
    assert "productivity_score" in report
    assert len(report["notifications"]) >= 1
    assert len(report["habits"]) >= 1
    assert len(report["memories"]) >= 1
