"""Pure logic: criteria 1-7."""

from datetime import date

import pytest

import bonsai

THU, FRI, SAT, SUN = date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 21), date(2026, 11, 22)
MON, TUE, WED = date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25)


# --- 1 -------------------------------------------------------------------
@pytest.mark.parametrize(
    "actual, completed, expected",
    [(30, True, 1), (45, True, 1), (60, True, 2), (90, True, 3), (10, True, 1),
     (59.9, True, 1), (89.99, True, 2), (60, False, 0), (10, False, 0)],
)
def test_plants_for_session(actual, completed, expected):
    assert bonsai.plants_for_session(actual, completed) == expected




# --- 3 -------------------------------------------------------------------
@pytest.mark.parametrize(
    "d, expected",
    [(WED, (MON, date(2026, 11, 29))),
     (MON, (MON, date(2026, 11, 29))),
     (SUN, (date(2026, 11, 16), SUN)),
     (date(2027, 1, 1), (date(2026, 12, 28), date(2027, 1, 3)))],
)
def test_week_bucketing(d, expected):
    assert bonsai.week_bounds(d) == expected


@pytest.mark.parametrize(
    "start_iso, expected",
    [("2026-11-23T23:50:00-08:00", date(2026, 11, 23)),
     ("2026-11-24T00:10:00+09:00", date(2026, 11, 24))],
)
def test_week_bucketing_session_date_no_tz_conversion(start_iso, expected):
    assert bonsai.session_date(start_iso) == expected


# --- 4 -------------------------------------------------------------------
@pytest.mark.parametrize(
    "dates, today, expected",
    [({THU, FRI, MON}, MON, 3),
     ({THU, FRI, MON}, TUE, 3),            # no Tue session yet: not broken
     ({THU, MON}, MON, 1),                 # Fri missing breaks it
     (set(), MON, 0),
     ({SAT, SUN}, MON, 0),                 # weekends never count
     ({THU, FRI, SAT, MON}, MON, 3),       # Sat session doesn't add
     ({THU, FRI}, SUN, 2),                 # weekend today doesn't break
     ({THU, FRI}, TUE, 0)],                # Mon missed, today Tue: broken
)
def test_streaks_current(dates, today, expected):
    assert bonsai.current_streak(dates, today) == expected


@pytest.mark.parametrize(
    "dates, expected",
    [({THU, FRI, MON}, 3), ({MON, TUE, THU}, 2), (set(), 0),
     ({SAT, SUN}, 0), ({THU, FRI, SAT, SUN, MON, TUE}, 4)],
)
def test_streaks_best(dates, expected):
    assert bonsai.best_streak(dates) == expected


# --- 5 -------------------------------------------------------------------
EMOJIS = {"learning": "🍄", "writing": "🌻"}


@pytest.mark.parametrize(
    "plants, expected",
    [([("work", 2), ("learning", 1), ("work", 1), ("writing", 1), ("learning", 1)],
      "🌵 🌵 🌵   🍄 🍄 🌻"),
     ([("work", 2)], "🌵 🌵"),
     ([("writing", 1), ("learning", 2)], "🌻 🍄 🍄"),
     ([], ""),
     ([("work", 0), ("learning", 0)], ""),
     ([("work", 1), ("learning", 0)], "🌵")],
)
def test_garden_row_layout(plants, expected):
    assert bonsai.garden_row(plants, EMOJIS) == expected


def test_garden_row_work_always_cactus():
    assert bonsai.garden_row([("work", 1), ("learning", 1)], {"work": "🍄", "learning": "🌷"}) == "🌵   🌷"


# --- 6 -------------------------------------------------------------------
@pytest.mark.parametrize(
    "hours, color",
    [(0, "green"), (31.9, "green"), (32, "yellow"), (37.9, "yellow"), (38, "red"), (45, "red")],
)
def test_cap_thresholds_bar_color(hours, color):
    assert bonsai.bar_color(hours) == color


@pytest.mark.parametrize("hours", [0, 37.9])
def test_cap_thresholds_no_warning_below_38(hours):
    assert bonsai.cap_warning(hours) is None


@pytest.mark.parametrize("hours", [38.0, 41.5])
def test_cap_thresholds_warning_at_38(hours):
    msg = bonsai.cap_warning(hours)
    assert isinstance(msg, str) and msg.strip()
    assert "\n" not in msg.strip()


# --- 7 -------------------------------------------------------------------
@pytest.mark.parametrize(
    "start, end, planned, expected",
    [(0, 60, 30, 1.0), (0, 3 * 3600, 30, 30), (1000, 1000 + 90, 30, 1.5),
     (1000, 1000 + 1800, 30, 30), (1000, 1000 + 1801, 30, 30)],
)
def test_actual_minutes_capped(start, end, planned, expected):
    result = bonsai.actual_minutes(start, end, planned)
    assert isinstance(result, float)
    assert result == pytest.approx(expected)


# --- growth trail in the live view ------------------------------------------
@pytest.mark.parametrize("progress, expected", [
    (0.0, "🌱"), (0.24, "🌱"),
    (0.25, "🌱 🍃"), (0.49, "🌱 🍃"),
    (0.5, "🌱 🍃 🌿"), (0.89, "🌱 🍃 🌿"),
    (0.9, "🌱 🍃 🌿 🌻"), (1.0, "🌱 🍃 🌿 🌻"),
])
def test_plant_trail_keeps_earlier_stages(progress, expected):
    assert bonsai.plant_trail(progress, "🌻") == expected


@pytest.mark.parametrize("progress, expected", [(0.1, "🥀"), (0.3, "🌱 🥀"), (0.6, "🌱 🍃 🥀")])
def test_plant_trail_stopped_wilts_current_stage(progress, expected):
    assert bonsai.plant_trail(progress, "🌵", stopped=True) == expected
