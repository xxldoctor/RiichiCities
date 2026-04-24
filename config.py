import json
import os
from pathlib import Path
from typing import Dict


BASE_DIR = Path(__file__).resolve().parent
TOKEN_FILE = BASE_DIR / "token.txt"
CHATS_FILE = BASE_DIR / "chats.json"
LINKS_FILE = BASE_DIR / "links.json"
CITY_CONTEXTS_DIR = BASE_DIR

ADMIN_USERNAME = "xxldoctor"


def _load_json_file(path: Path, default):
  try:
    with open(path, "r", encoding="utf-8") as file:
      return json.load(file)
  except FileNotFoundError:
    return default


def load_allowed_chats() -> Dict[str, str]:
  file_mapping = _load_json_file(CHATS_FILE, {})
  if not isinstance(file_mapping, dict) or "contexts" not in file_mapping or not isinstance(file_mapping["contexts"], dict):
    return {}

  normalized_mapping: Dict[str, str] = {}
  for meta_id, context_data in file_mapping["contexts"].items():
    if not isinstance(context_data, dict):
      continue

    chat_ids = context_data.get("chat_ids", [])
    if not isinstance(chat_ids, list):
      continue

    for raw_chat_id in chat_ids:
      normalized_mapping[str(raw_chat_id)] = str(meta_id)

  return normalized_mapping


def load_token() -> str:
  env_token = os.environ.get("bot_token")
  if env_token:
    return env_token

  with open(TOKEN_FILE, "r", encoding="utf-8") as token_file:
    return token_file.read().strip()
