from telegram import Update
from telegram.ext import CallbackContext, CommandHandler


def register_hand_handlers(dispatcher) -> None:
  def hand(update: Update, _: CallbackContext) -> None:
    command_parts = update.message.text.strip().split(None, 1)
    if len(command_parts) < 2:
      update.message.reply_text("Вы не указали руку для отображения.")
      return
    if len(command_parts) > 2:
      update.message.reply_text("Неверный формат руки.")
      return

    hand_url = "https://api.tempai.net/image/" + command_parts[1].strip() + ".png"
    update.message.reply_text(hand_url)

  dispatcher.add_handler(CommandHandler("hand", hand))
