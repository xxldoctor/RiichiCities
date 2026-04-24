from telegram import Update
from telegram.ext import CommandHandler, ContextTypes


def register_hand_handlers(dispatcher) -> None:
  async def hand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
      return

    if not context.args:
      await update.effective_message.reply_text("Вы не указали руку для отображения.")
      return

    hand_code = "".join(context.args).strip()
    hand_url = f"https://api.tempai.net/image/{hand_code}.png"
    await update.effective_message.reply_text(hand_url)

  dispatcher.add_handler(CommandHandler("hand", hand))
