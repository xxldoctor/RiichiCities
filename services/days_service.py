from datetime import datetime, timedelta
from typing import List


WEEKDAY_NAMES_RU = [
  "Понедельник",
  "Вторник",
  "Среда",
  "Четверг",
  "Пятница",
  "Суббота",
  "Воскресенье",
]


def week_day_name(date_value: datetime) -> str:
  return WEEKDAY_NAMES_RU[date_value.weekday()]


def _build_week_options(start_date: datetime) -> List[str]:
  options: List[str] = []
  current_date = start_date
  for _ in range(7):
    current_date = current_date + timedelta(days=1)
    options.append(f"{current_date.day}.{current_date.month} - {week_day_name(current_date)}")

  options.extend(["я не смогу", "играю не все дни"])
  return options


def this_week() -> List[str]:
  start_of_week = datetime.now() - timedelta(days=datetime.now().weekday() + 1)
  return _build_week_options(start_of_week)


def next_week() -> List[str]:
  start_of_next_week = datetime.now() - timedelta(days=datetime.now().weekday() - 6)
  return _build_week_options(start_of_next_week)
