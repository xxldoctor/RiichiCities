from typing import Callable, Dict

from telegram import Update
from telegram.ext import CallbackContext


def make_check_chat_id(city_repo, allowed_chats: Dict[str, str]) -> Callable:
  def check_chat_id(func):
    def wrapper(update: Update, context: CallbackContext):
      chat_id = str(update.effective_chat.id)
      user_id = update.effective_user.id

      if chat_id == str(user_id):
        if city_repo.user_exists_in_meta("mahjong", user_id):
          return func(update, context, meta_id="mahjong")

        update.message.reply_text(
          "Извините, но вы не числитесь в каком-либо городе. "
          "Для использования бота в личке выполните <code>/my_city город</code> "
          "в одном из маджонговых чатов.",
          parse_mode="html",
        )
        return

      if chat_id not in allowed_chats:
        update.message.reply_text("Извините, но эту команду можно использовать только в определенных чатах.")
        return

      return func(update, context, meta_id=allowed_chats[chat_id])

    return wrapper

  return check_chat_id
