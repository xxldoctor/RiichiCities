from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from services.links_service import generate_links_menu, load_links_data


SECTION_COMMANDS = {
  "online": "online",
  "learn": "learn",
  "theory": "theory",
  "tools": "tools",
  "trainers": "trainers",
  "social": "social",
  "streams": "streams",
  "blogs": "blogs",
  "other": "other",
  "fun": "fun",
  "stickers": "stickers",
}


def register_links_handlers(dispatcher, links_file: str) -> None:
  async def send_menu(update: Update, prefix: str, path: str = "", root_path: str = "", show_controls: bool = True) -> None:
    if update.effective_message is None:
      return

    data = load_links_data(links_file)
    text, reply_markup = generate_links_menu(
      data,
      path=path,
      prefix=prefix,
      root_path=root_path,
      show_controls=show_controls,
    )

    is_callback = update.callback_query is not None
    if reply_markup is None:
      if is_callback:
        await update.callback_query.edit_message_text(
          text,
          parse_mode="HTML",
          disable_web_page_preview=True,
        )
      else:
        await update.effective_message.reply_text(
          text,
          parse_mode="HTML",
          disable_web_page_preview=True,
        )
      return

    if is_callback:
      await update.callback_query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
      )
      return

    await update.effective_message.reply_text(
      text,
      reply_markup=reply_markup,
      parse_mode="HTML",
      disable_web_page_preview=True,
    )

  async def links(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await send_menu(update, prefix="links_")

  def register_section_command(command: str, target_path: str) -> None:
    prefix = f"{command}_"

    async def section_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
      if update.effective_message is None:
        return

      data = load_links_data(links_file)
      current = data
      path_parts = target_path.split(".") if target_path else []
      for part in path_parts:
        if not part:
          continue
        for section in current.get("sections", []):
          if section.get("id") == part:
            current = section
            break

      show_controls = "sections" in current
      await send_menu(
        update,
        prefix=prefix,
        path=target_path,
        root_path=target_path,
        show_controls=show_controls,
      )

    async def section_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
      query = update.callback_query
      if query is None:
        return

      await query.answer()
      data = query.data or ""

      if data == f"{prefix}close":
        await query.message.delete()
        return
      if data == f"{prefix}save":
        await query.edit_message_reply_markup(reply_markup=None)
        return

      if data.startswith(prefix):
        path = data[len(prefix):]
      else:
        path = ""

      await send_menu(
        update,
        prefix=prefix,
        path=path,
        root_path=target_path,
        show_controls=True,
      )

    dispatcher.add_handler(CommandHandler(command, section_command))
    dispatcher.add_handler(CallbackQueryHandler(section_callback, pattern=f"^{prefix}"))

  dispatcher.add_handler(CommandHandler("links", links))

  for command, target_path in SECTION_COMMANDS.items():
    register_section_command(command, target_path)

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

    if reply_markup is None:
      await query.edit_message_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
      )
      return

    await query.edit_message_text(
      text,
      reply_markup=reply_markup,
      parse_mode="HTML",
      disable_web_page_preview=True,
    )

  dispatcher.add_handler(CallbackQueryHandler(links_callback, pattern="^links_"))
