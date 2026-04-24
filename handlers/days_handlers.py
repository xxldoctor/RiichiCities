from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from services.days_service import next_week, this_week


def register_days_handlers(dispatcher) -> None:
  async def this_week_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
      return

    await context.bot.send_poll(
      chat_id=update.effective_chat.id,
      question="Играем?",
      options=this_week(),
      is_anonymous=False,
      allows_multiple_answers=True,
      message_thread_id=update.effective_message.message_thread_id,
    )

  async def next_week_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
      return

    await context.bot.send_poll(
      chat_id=update.effective_chat.id,
      question="Играем?",
      options=next_week(),
      is_anonymous=False,
      allows_multiple_answers=True,
      message_thread_id=update.effective_message.message_thread_id,
    )

  dispatcher.add_handler(CommandHandler("this_week_poll", this_week_poll))
  dispatcher.add_handler(CommandHandler("next_week_poll", next_week_poll))
