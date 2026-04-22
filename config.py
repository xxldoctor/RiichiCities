import os


TOKEN_FILE = "token.txt"
ADMIN_USERNAME = "xxldoctor"
DATA_FILE = "city_users.json"
LINKS_FILE = "links.json"

# Список допустимых chat_id, где бот может быть использован
ALLOWED_CHATS = {
  "-1001078882316": "mahjong",
  "-1001182235196": "mahjong",
  "-1001167521254": "mahjong",
  "-840250661": "test",
  "-938606890": "test",
}


def load_token():
  env_token = os.environ.get("bot_token")
  if env_token:
    return env_token

  with open(TOKEN_FILE, "r", encoding="utf-8") as token_file:
    return token_file.read().strip()
