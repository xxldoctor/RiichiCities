from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from services.links_service import generate_links_menu, load_links_data


def register_links_handlers(dispatcher, links_file: str) -> None:
  async def links(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
      return

    data = load_links_data(links_file)
    text, reply_markup = generate_links_menu(data)
    await update.effective_message.reply_text(
      text,
      reply_markup=reply_markup,
      parse_mode="HTML",
      disable_web_page_preview=True,
    )

  async def links_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
      return

    await query.answer()

    if query.data == "links_close":
      await query.message.delete()
      return
    if query.data == "links_save":
      await query.edit_message_reply_markup(reply_markup=None)
      return

    if query.data == "links_root":
      path = ""
    elif query.data and query.data.startswith("links_"):
      path = query.data[6:]
    else:
      path = ""

    data = load_links_data(links_file)
    text, reply_markup = generate_links_menu(data, path)

    await query.edit_message_text(
      text,
      reply_markup=reply_markup,
      parse_mode="HTML",
      disable_web_page_preview=True,
    )

  dispatcher.add_handler(CommandHandler("links", links))
  dispatcher.add_handler(CallbackQueryHandler(links_callback, pattern="^links_"))
