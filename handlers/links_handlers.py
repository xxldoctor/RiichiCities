from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from services.links_service import generate_links_menu, load_links_data


SECTION_COMMANDS = {
  "online": "play.online",
  "learn": "learn",
  "theory": "learn.theory",
  "tools": "learn.tools",
  "trainers": "learn.trainers",
  "social": "community.social",
  "streams": "community.streams",
  "blogs": "community.blogs",
  "other": "other",
  "fun": "other.fun",
  "stickers": "other.stickers",
}


def register_links_handlers(dispatcher, links_file: str) -> None:
  async def send_menu(
    update: Update,
    *,
    prefix: str,
    path: str = "",
    root_path: str = "",
    show_controls: bool = True,
  ) -> None:
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

  async def handle_menu_callback(update: Update, prefix: str, root_path: str = "") -> None:
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
      path = root_path

    await send_menu(
      update,
      prefix=prefix,
      path=path,
      root_path=root_path,
      show_controls=True,
    )

  def register_menu_command(command: str, prefix: str, root_path: str = "") -> None:
    async def menu_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
      await send_menu(
        update,
        prefix=prefix,
        path=root_path,
        root_path=root_path,
        show_controls=True,
      )

    async def menu_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
      await handle_menu_callback(update, prefix=prefix, root_path=root_path)

    dispatcher.add_handler(CommandHandler(command, menu_command))
    dispatcher.add_handler(CallbackQueryHandler(menu_callback, pattern=f"^{prefix}"))

  register_menu_command("links", "links_")

  for command, target_path in SECTION_COMMANDS.items():
    register_menu_command(command, f"{command}_", target_path)
