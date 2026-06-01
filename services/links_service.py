import json
from typing import Any, Dict, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def load_links_data(links_file: str) -> Dict[str, Any]:
  with open(links_file, "r", encoding="utf-8") as file:
    return json.load(file)


def _resolve_current_node(data: Dict[str, Any], path: str) -> Dict[str, Any]:
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

  return current


def generate_links_menu(
  data: Dict[str, Any],
  path: str = "",
  prefix: str = "links_",
  root_path: str = "",
  show_controls: bool = True,
) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
  current = _resolve_current_node(data, path)
  title = current.get("title", "Полезные ссылки")
  message = f"<b>{title}</b>\n"
  keyboard = []

  if "sections" in current:
    for section in current["sections"]:
      next_path = f"{path}.{section['id']}" if path else section["id"]
      callback_data = f"{prefix}{next_path}"
      keyboard.append([InlineKeyboardButton(section["title"], callback_data=callback_data)])

  if "links" in current:
    message += "\n"
    for link in current["links"]:
      message += f" - {link}\n"

  has_sections = "sections" in current
  is_at_root = path == root_path

  if not show_controls:
    return message, None

  if not has_sections and is_at_root:
    return message, None

  navigation_row = []
  if path and not is_at_root:
    path_parts = path.split(".")
    root_parts = root_path.split(".") if root_path else []
    parent_path = ".".join(path_parts[:-1])
    if root_path and len(path_parts) - 1 < len(root_parts):
      callback_data = f"{prefix}{root_path}"
    else:
      callback_data = f"{prefix}{parent_path}" if parent_path else f"{prefix}{root_path}"
    navigation_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=callback_data))

  navigation_row.append(InlineKeyboardButton("❌ Закрыть", callback_data=f"{prefix}close"))

  if show_controls:
    navigation_row.append(InlineKeyboardButton("Сохранить", callback_data=f"{prefix}save"))

  keyboard.append(navigation_row)
  return message, InlineKeyboardMarkup(keyboard)
