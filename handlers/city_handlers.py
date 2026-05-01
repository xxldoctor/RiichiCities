from html import escape
from typing import Dict, List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from services.city_catalog_service import CityCatalog, CityInfo, CityLink, CityPlayer, paginate_items, total_pages


CITY_PAGE_SIZE = 12


def register_city_handlers(dispatcher, city_repo, city_catalog: CityCatalog, check_chat_id, admin_username):
  def build_display_name(user: Optional[User], player: Optional[CityPlayer], user_id: Optional[int]) -> str:
    if user is not None:
      if user.full_name:
        return user.full_name
      if user.username:
        return f"@{user.username}"

    if player and player.display_name:
      return player.display_name
    if player and player.username:
      return f"@{player.username}"
    if user_id is not None:
      return f"ID:{user_id}"
    return "Неизвестный игрок"

  async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_user is None or update.effective_chat is None:
      return False

    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return (
      member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}
      or update.effective_user.username == admin_username
    )

  def make_cities_page_callback(page: int, owner_id: int) -> str:
    return f"cities:page:{page}:{owner_id}"

  def make_city_view_callback(page: int, owner_id: int, city_name: str) -> str:
    return f"city:view:{page}:{owner_id}:{city_name}"

  def make_close_callback(owner_id: int) -> str:
    return f"cities:close:{owner_id}"

  def make_save_callback(owner_id: int) -> str:
    return f"cities:save:{owner_id}"

  def make_set_city_callback(page: int, owner_id: int, city_name: str) -> str:
    return f"city:set:{page}:{owner_id}:{city_name}"

  def parse_owner_id(data: str) -> Optional[int]:
    parts = data.split(":")
    try:
      if parts[:2] == ["cities", "page"] and len(parts) >= 4:
        return int(parts[3])
      if parts[:2] == ["city", "view"] and len(parts) >= 5:
        return int(parts[3])
      if parts[:2] == ["city", "set"] and len(parts) >= 5:
        return int(parts[3])
      if parts[:2] == ["cities", "close"] and len(parts) >= 3:
        return int(parts[2])
      if parts[:2] == ["cities", "save"] and len(parts) >= 3:
        return int(parts[2])
      if parts[:2] == ["cities", "noop"] and len(parts) >= 3:
        return int(parts[2])
    except ValueError:
      return None
    return None

  async def can_manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, owner_id: Optional[int]) -> bool:
    if owner_id is None or update.effective_user is None:
      return False
    if update.effective_user.id == owner_id:
      return True
    return await is_admin(update, context)

  def parse_user_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    message = update.effective_message
    if message is None:
      return None, "Не удалось прочитать сообщение."

    if not context.args:
      return None, "Вы не указали пользователя."

    user_tokens: Dict[str, str] = {}
    entities = message.entities or []
    for entity in entities:
      if entity.type == "mention":
        username = message.text[entity.offset + 1 : entity.offset + entity.length].lower()
        user_tokens[username] = username
      elif entity.type == "text_mention" and entity.user is not None:
        label = message.text[entity.offset : entity.offset + entity.length]
        user_tokens[label] = f"ID:{entity.user.id}"

    if not user_tokens:
      if len(context.args) != 1:
        return None, (
          "Вы неправильно используете команду.\n"
          "Укажите один юзернейм или используйте текст с упоминаниями пользователей."
        )
      token = context.args[0].strip().lstrip("@").lower()
      user_tokens[token] = token

    return user_tokens, None

  async def try_refresh_player(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    meta_id: str,
    city_name: str,
    player: CityPlayer,
  ) -> CityPlayer:
    if player.user_id is None:
      return player

    if update.effective_chat is None or update.effective_chat.type == "private":
      return player

    try:
      member = await context.bot.get_chat_member(update.effective_chat.id, player.user_id)
    except TelegramError:
      return player

    user = member.user
    city_repo.upsert_user_city(
      meta_id,
      city_name,
      user.id,
      display_name=user.full_name,
      username=user.username,
    )
    return CityPlayer(
      user_id=user.id,
      display_name=user.full_name,
      username=user.username,
      note=player.note,
    )

  async def resolve_city_players(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    meta_id: str,
    city_name: str,
  ) -> List[CityPlayer]:
    players = city_repo.get_city_players(meta_id, city_name)
    refreshed_players: List[CityPlayer] = []
    for player in players:
      refreshed_players.append(await try_refresh_player(update, context, meta_id, city_name, player))
    return sorted(refreshed_players, key=lambda player: (player.display_name or "", player.username or ""))

  def visible_city_names(meta_id: str) -> List[str]:
    visible_names: List[str] = []
    for city_name, city_info in city_catalog.load(meta_id).items():
      if city_info.visible:
        visible_names.append(city_name)
    return sorted(visible_names)

  def build_city_list_markup(meta_id: str, page: int, owner_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    city_names = visible_city_names(meta_id)
    pages = total_pages(city_names, CITY_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    page_city_names = paginate_items(city_names, page, CITY_PAGE_SIZE)

    keyboard = []
    for city_name in page_city_names:
      users_count = len(city_repo.get_city_players(meta_id, city_name))
      suffix = f" ({users_count})" if users_count else ""
      keyboard.append([InlineKeyboardButton(
        f"{city_name}{suffix}",
        callback_data=make_city_view_callback(page, owner_id, city_name),
      )])

    navigation_row = []
    if page > 0:
      navigation_row.append(InlineKeyboardButton("⬅️", callback_data=make_cities_page_callback(page - 1, owner_id)))
    navigation_row.append(InlineKeyboardButton(f"{page + 1}/{pages}", callback_data=f"cities:noop:{owner_id}"))
    if page + 1 < pages:
      navigation_row.append(InlineKeyboardButton("➡️", callback_data=make_cities_page_callback(page + 1, owner_id)))
    keyboard.append(navigation_row)
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data=make_close_callback(owner_id))])

    text = "<b>Города</b>\nВыберите город."
    return text, InlineKeyboardMarkup(keyboard)

  def format_city_link_lines(items: List[CityLink]) -> List[str]:
    lines: List[str] = []
    for item in items:
      if not item.visible:
        continue
      lines.append(f"• <a href=\"{escape(item.url)}\">{escape(item.title)}</a>")
    return lines

  async def build_city_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    meta_id: str,
    city_name: str,
    page: int,
    owner_id: int,
  ) -> Tuple[str, InlineKeyboardMarkup]:
    city_info = city_catalog.get_city(meta_id, city_name)
    if city_info is None:
      text = f"<b>{escape(city_name)}</b>\nНет данных о городе."
      markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Назад", callback_data=make_cities_page_callback(page, owner_id)),
        InlineKeyboardButton("❌ Закрыть", callback_data=make_close_callback(owner_id)),
      ]])
      return text, markup

    players = await resolve_city_players(update, context, meta_id, city_name)
    links = [item for item in city_info.clubs if item.visible] + [item for item in city_info.ratings if item.visible]

    lines = [f"<b>{escape(city_name)}</b>", "", "Игроки:"]
    if city_info.users_text:
      lines.append(escape(city_info.users_text))
    elif players:
      for player in players:
        display_name = build_display_name(None, player, player.user_id)
        if player.user_id is not None:
          mention = f"<a href=\"tg://user?id={player.user_id}\">{escape(display_name)}</a>"
        else:
          mention = escape(display_name)

        if player.username:
          lines.append(f"• {mention} (@{escape(player.username)})")
        elif player.note:
          lines.append(f"• {mention} - {escape(player.note)}")
        else:
          lines.append(f"• {mention}")
    else:
      lines.append("Нет данных.")

    lines.extend(["", "Чаты, клубы и рейтинги:"])
    link_lines = format_city_link_lines(links)
    if link_lines:
      lines.extend(link_lines)
    else:
      lines.append("Нет данных.")

    keyboard = [[
      InlineKeyboardButton("⬅️ Назад", callback_data=make_cities_page_callback(page, owner_id)),
      InlineKeyboardButton("Я здесь", callback_data=make_set_city_callback(page, owner_id, city_name)),
    ], [
      InlineKeyboardButton("❌ Закрыть", callback_data=make_close_callback(owner_id)),
      InlineKeyboardButton("Сохранить", callback_data=make_save_callback(owner_id)),
    ]]
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)

  async def send_or_edit(update: Update, text: str, reply_markup: InlineKeyboardMarkup, parse_mode: str = "HTML") -> None:
    if update.callback_query is not None:
      await update.callback_query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        disable_web_page_preview=True,
      )
      return

    if update.effective_message is not None:
      await update.effective_message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        disable_web_page_preview=True,
      )

  @check_chat_id
  async def cities(update: Update, _: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_user is None:
      return
    text, reply_markup = build_city_list_markup(meta_id, page=0, owner_id=update.effective_user.id)
    await send_or_edit(update, text, reply_markup)

  @check_chat_id
  async def clubs(update: Update, _: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_message is None:
      return

    lines = ["<b>Клубы</b>"]
    found_any = False
    for city_name in visible_city_names(meta_id):
      city_info = city_catalog.get_city(meta_id, city_name)
      if city_info is None:
        continue
      for club in city_info.clubs:
        if not club.visible:
          continue
        found_any = True
        lines.append(f"• {escape(city_name)} - <a href=\"{escape(club.url)}\">{escape(club.title)}</a>")

    if not found_any:
      lines.append("Нет данных.")

    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)

  @check_chat_id
  async def users_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_message is None or update.effective_user is None:
      return
    if not context.args:
      await update.effective_message.reply_text("Вы не указали город.")
      return

    city_name = " ".join(context.args).strip()
    text, reply_markup = await build_city_view(update, context, meta_id, city_name, page=0, owner_id=update.effective_user.id)
    await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)

  @check_chat_id
  async def city_by_user(update: Update, context: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_message is None:
      return

    user_tokens, error = parse_user_tokens(update, context)
    if error:
      await update.effective_message.reply_text(error.replace("пользователя.", "пользователя для получения города."))
      return

    for user_label, token in user_tokens.items():
      player = city_repo.find_player(meta_id, token)
      if player is None or player.user_id is None:
        await update.effective_message.reply_text(f"Пользователь {user_label} не числится в каком-либо городе.")
        continue

      city_name = city_repo.find_city_by_user_id(meta_id, player.user_id)
      if city_name:
        await update.effective_message.reply_text(f"Город, привязанный к пользователю {user_label}: {city_name}")
      else:
        await update.effective_message.reply_text(f"Пользователь {user_label} не числится в каком-либо городе.")

  @check_chat_id
  async def my_city(update: Update, context: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_user is None or update.effective_message is None:
      return
    if not context.args:
      await update.effective_message.reply_text("Вы не указали новый город для смены.")
      return

    new_city = " ".join(context.args).strip()
    if new_city.startswith("/"):
      await update.effective_message.reply_text("Некорректное имя города. Город не может начинаться с '/'.")
      return

    city_info = city_catalog.get_city(meta_id, new_city)
    if city_info is not None and city_info.join_error_text:
      await update.effective_message.reply_text(city_info.join_error_text)
      return

    user = update.effective_user
    city_repo.upsert_user_city(meta_id, new_city, user.id, display_name=user.full_name, username=user.username)
    await update.effective_message.reply_text(f"Ваш город изменен на: {new_city}")

    city_info = city_catalog.get_city(meta_id, new_city)
    if city_info is None or city_info.auto_show_members:
      text, reply_markup = await build_city_view(update, context, meta_id, new_city, page=0, owner_id=user.id)
      await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)

  @check_chat_id
  async def leave_city(update: Update, _: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_user is None or update.effective_message is None:
      return

    city_name = city_repo.find_city_by_user_id(meta_id, update.effective_user.id)
    if not city_name:
      await update.effective_message.reply_text("Вы не числитесь в каком-либо городе.")
      return

    city_repo.remove_user_from_city(meta_id, city_name, update.effective_user.id)
    await update.effective_message.reply_text(f"Вы удалены из города {city_name}.")

  @check_chat_id
  async def rename_city(update: Update, context: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_message is None:
      return
    if not await is_admin(update, context):
      await update.effective_message.reply_text("Вы не являетесь администратором.")
      return

    command_text = " ".join(context.args).strip()
    if "," not in command_text:
      await update.effective_message.reply_text(
        "Вы не указали старое и новое имя города для переименования.\nИспользуйте запятую (,)."
      )
      return

    old_city, new_city = [part.strip() for part in command_text.split(",", 1)]
    if not old_city or not new_city:
      await update.effective_message.reply_text("Вы не указали старое и/или новое имя города.")
      return
    if old_city.startswith("/") or new_city.startswith("/"):
      await update.effective_message.reply_text("Некорректное имя города. Имена городов не могут начинаться с '/'.")
      return

    if not city_repo.rename_city(meta_id, old_city, new_city):
      await update.effective_message.reply_text(f"Город '{old_city}' не найден.")
      return

    await update.effective_message.reply_text(f"Город '{old_city}' переименован в '{new_city}'.")

  @check_chat_id
  async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_message is None:
      return
    if not await is_admin(update, context):
      await update.effective_message.reply_text("Вы не являетесь администратором.")
      return

    user_tokens, error = parse_user_tokens(update, context)
    if error:
      await update.effective_message.reply_text(error.replace("пользователя.", "пользователя для удаления."))
      return

    for user_label, token in user_tokens.items():
      player = city_repo.find_player(meta_id, token)
      if player is None or player.user_id is None:
        await update.effective_message.reply_text(f"Пользователь {user_label} не числится в каком-либо городе.")
        continue

      city_name = city_repo.find_city_by_user_id(meta_id, player.user_id)
      if city_name is None:
        await update.effective_message.reply_text(f"Пользователь {user_label} не числится в каком-либо городе.")
        continue

      city_repo.remove_user_from_city(meta_id, city_name, player.user_id)
      await update.effective_message.reply_text(f"Пользователь {user_label} удален из города {city_name}.")

  @check_chat_id
  async def remove_city(update: Update, context: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_message is None:
      return
    if not await is_admin(update, context):
      await update.effective_message.reply_text("Вы не являетесь администратором.")
      return
    if not context.args:
      await update.effective_message.reply_text("Вы не указали город для удаления.")
      return

    city_name = " ".join(context.args).strip()
    if city_repo.remove_city(meta_id, city_name):
      await update.effective_message.reply_text(f"Город {city_name} удален из списка городов.")
      return

    await update.effective_message.reply_text(f"Город {city_name} не найден.")

  @check_chat_id
  async def debug(update: Update, _: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_user is None or update.effective_message is None:
      return
    if update.effective_user.username != admin_username:
      await update.effective_message.reply_text("Вы не являетесь администратором.")
      return
    await update.effective_message.reply_text(f"Структура city files:\n{city_repo.get_chat_data(meta_id)}")

  async def debug_all(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
      return
    if update.effective_user.username != admin_username:
      await update.effective_message.reply_text("Вы не являетесь администратором.")
      return
    await update.effective_message.reply_text(f"Структура city files:\n{city_repo.get_all()}")

  @check_chat_id
  async def city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    query = update.callback_query
    if query is None:
      return

    data = query.data or ""
    owner_id = parse_owner_id(data)
    if data.startswith("city:set:"):
      if update.effective_user is None:
        return
      _, _, page, callback_owner_id, city_name = data.split(":", 4)
      city_info = city_catalog.get_city(meta_id, city_name)
      if city_info is not None and city_info.join_error_text:
        await query.answer(city_info.join_error_text, show_alert=True)
        return
      city_repo.upsert_user_city(
        meta_id,
        city_name,
        update.effective_user.id,
        display_name=update.effective_user.full_name,
        username=update.effective_user.username,
      )
      await query.answer("Город обновлён.")
      text, reply_markup = await build_city_view(update, context, meta_id, city_name, int(page), int(callback_owner_id))
      await send_or_edit(update, text, reply_markup)
      return

    if not await can_manage_menu(update, context, owner_id):
      await query.answer("Этим меню может управлять только автор или администратор.", show_alert=True)
      return

    await query.answer()

    if data.startswith("cities:close:"):
      await query.message.delete()
      return
    if data.startswith("cities:save:"):
      await query.edit_message_reply_markup(reply_markup=None)
      return
    if data.startswith("cities:noop:"):
      return
    if data.startswith("cities:page:"):
      _, _, page, callback_owner_id = data.split(":", 3)
      text, reply_markup = build_city_list_markup(meta_id, int(page), int(callback_owner_id))
      await send_or_edit(update, text, reply_markup)
      return
    if data.startswith("city:view:"):
      _, _, page, callback_owner_id, city_name = data.split(":", 4)
      text, reply_markup = await build_city_view(update, context, meta_id, city_name, int(page), int(callback_owner_id))
      await send_or_edit(update, text, reply_markup)

  dispatcher.add_handler(CommandHandler("cities", cities))
  dispatcher.add_handler(CommandHandler("clubs", clubs))
  dispatcher.add_handler(CommandHandler("users_from_city", users_from_city))
  dispatcher.add_handler(CommandHandler("city_by_user", city_by_user))
  dispatcher.add_handler(CommandHandler("my_city", my_city))
  dispatcher.add_handler(CommandHandler("leave_city", leave_city))
  dispatcher.add_handler(CommandHandler("rename_city", rename_city))
  dispatcher.add_handler(CommandHandler("remove_user", remove_user))
  dispatcher.add_handler(CommandHandler("remove_city", remove_city))
  dispatcher.add_handler(CommandHandler("debug", debug))
  dispatcher.add_handler(CommandHandler("debug_all", debug_all))
  dispatcher.add_handler(CallbackQueryHandler(city_callback, pattern=r"^(cities:|city:)"))
