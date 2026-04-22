from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler

from services.links_service import generate_links_menu, load_links_data


def register_links_handlers(dispatcher, links_file: str) -> None:
  def links(update: Update, _: CallbackContext) -> None:
    data = load_links_data(links_file)
    text, reply_markup = generate_links_menu(data)
    update.message.reply_text(text, reply_markup=reply_markup, parse_mode="html", disable_web_page_preview=True)

  def links_callback(update: Update, _: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    if query.data == "links_close":
      query.message.delete()
      return
    if query.data == "links_save":
      query.edit_message_reply_markup(reply_markup=None)
      return

    if query.data == "links_root":
      path = ""
    elif query.data.startswith("links_"):
      path = query.data[6:]
    else:
      path = ""

    data = load_links_data(links_file)
    text, reply_markup = generate_links_menu(data, path)

    if query.message.text_html == text and query.message.reply_markup == reply_markup:
      return

    query.edit_message_text(text, reply_markup=reply_markup, parse_mode="html", disable_web_page_preview=True)

  dispatcher.add_handler(CommandHandler("links", links))
  dispatcher.add_handler(CallbackQueryHandler(links_callback, pattern="^links_"))
