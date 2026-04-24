from functools import wraps
from typing import Awaitable, Callable, Dict

from telegram import Update
from telegram.ext import ContextTypes


def make_check_chat_id(city_repo, allowed_chats: Dict[str, str]) -> Callable:
  def resolve_private_meta_id(user_id: int) -> str | None:
    meta_ids = city_repo.find_meta_ids_by_user(user_id)
    if not meta_ids:
      return None

    if "mahjong" in meta_ids:
      return "mahjong"

    return sorted(meta_ids)[0]

  def check_chat_id(func: Callable[..., Awaitable[None]]):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
      if update.effective_chat is None or update.effective_user is None or update.effective_message is None:
        return

      chat_id = str(update.effective_chat.id)
      user_id = update.effective_user.id

      if chat_id == str(user_id):
        meta_id = resolve_private_meta_id(user_id)
        if meta_id is not None:
          return await func(update, context, meta_id=meta_id)

        await update.effective_message.reply_text(
          "Извините, но вы не числитесь в каком-либо городе. "
          "Для использования бота в личке выполните <code>/my_city город</code> "
          "в одном из маджонговых чатов.",
          parse_mode="HTML",
        )
        return

      if chat_id not in allowed_chats:
        await update.effective_message.reply_text(
          "Извините, но эту команду можно использовать только в определенных чатах."
        )
        return

      return await func(update, context, meta_id=allowed_chats[chat_id])

    return wrapper

  return check_chat_id
