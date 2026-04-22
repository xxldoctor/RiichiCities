from telegram import Update
from telegram.ext import CallbackContext, CommandHandler

from services.days_service import next_week, this_week


def register_days_handlers(dispatcher) -> None:
  def this_week_poll(update: Update, context: CallbackContext) -> None:
    context.bot.send_poll(
      chat_id=update.effective_chat.id,
      question="Играем?",
      options=this_week(),
      is_anonymous=False,
      allows_multiple_answers=True,
      message_thread_id=update.effective_message.message_thread_id,
    )

  def next_week_poll(update: Update, context: CallbackContext) -> None:
    context.bot.send_poll(
      chat_id=update.effective_chat.id,
      question="Играем?",
      options=next_week(),
      is_anonymous=False,
      allows_multiple_answers=True,
      message_thread_id=update.effective_message.message_thread_id,
    )

  dispatcher.add_handler(CommandHandler("this_week_poll", this_week_poll))
  dispatcher.add_handler(CommandHandler("next_week_poll", next_week_poll))
