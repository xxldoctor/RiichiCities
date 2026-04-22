import json
from typing import Any, Dict, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def load_links_data(links_file: str) -> Dict[str, Any]:
  with open(links_file, "r", encoding="utf-8") as file:
    return json.load(file)


def generate_links_menu(data: Dict[str, Any], path: str = "", prefix: str = "links_") -> Tuple[str, InlineKeyboardMarkup]:
  current = data
  path_parts = path.split(".") if path else []

  for part in path_parts:
    if not part:
      continue
    found = False
    for section in current.get("sections", []):
      if section.get("id") == part:
        current = section
        found = True
        break
    if not found:
      break

  title = current.get("title", "Полезные ссылки")
  message = f"<b>{title}</b>\n"
  keyboard = []

  if "sections" in current:
    for section in current["sections"]:
      callback_data = f"{prefix}{path}.{section['id']}" if path else f"{prefix}{section['id']}"
      keyboard.append([InlineKeyboardButton(section["title"], callback_data=callback_data)])

  if "links" in current:
    message += "\n"
    for link in current["links"]:
      message += f" - {link}\n"

  navigation_row = []
  if path:
    parent_path = ".".join(path_parts[:-1])
    callback_data = f"{prefix}{parent_path}" if parent_path else f"{prefix}root"
    navigation_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=callback_data))

  navigation_row.append(InlineKeyboardButton("❌ Закрыть", callback_data=f"{prefix}close"))

  if "sections" not in current:
    navigation_row.append(InlineKeyboardButton("Сохранить", callback_data=f"{prefix}save"))

  keyboard.append(navigation_row)
  return message, InlineKeyboardMarkup(keyboard)
