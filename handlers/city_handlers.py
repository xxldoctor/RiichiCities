from html import escape
from typing import Dict, List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from services.city_catalog_service import CityCatalog, CityInfo, CityPlayer, paginate_items, total_pages


CITY_PAGE_SIZE = 12
PLAYER_PAGE_SIZE = 10


def register_city_handlers(dispatcher, city_repo, city_catalog: CityCatalog, check_chat_id, admin_username):
  def build_display_name(user: Optional[User], profile: Optional[Dict[str, Optional[str]]], user_id: Optional[int]) -> str:
    if user is not None:
      if user.full_name:
        return user.full_name
      if user.username:
        return f"@{user.username}"

    if profile and profile.get("display_name"):
      return profile["display_name"]
    if profile and profile.get("username"):
      return f"@{profile['username']}"
    if user_id is not None:
      return f"ID:{user_id}"
    return "Неизвестный игрок"

  def build_profile_url(player: CityPlayer) -> Optional[str]:
    if player.username:
      return f"https://t.me/{player.username}"
    if player.user_id is not None:
      return f"tg://user?id={player.user_id}"
    return None

  async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_user is None or update.effective_chat is None:
      return False

    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return (
      member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}
      or update.effective_user.username == admin_username
    )

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

  async def try_refresh_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    meta_id: str,
    city_name: str,
    user_id: int,
  ) -> Dict[str, Optional[str]]:
    cached_player = next(
      (player for player in city_repo.get_city_players(meta_id, city_name) if player.user_id == user_id),
      None,
    )
    cached_profile = {
      "display_name": cached_player.display_name if cached_player is not None else None,
      "username": cached_player.username if cached_player is not None else None,
    }

    if update.effective_chat is None or update.effective_chat.type == "private":
      return cached_profile

    try:
      member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
    except TelegramError:
      return cached_profile

    user = member.user
    city_repo.upsert_user_city(
      meta_id,
      city_name,
      user.id,
      display_name=user.full_name,
      username=user.username,
    )
    return {
      "display_name": user.full_name,
      "username": user.username,
    }

  async def resolve_city_players(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    meta_id: str,
    city_name: str,
    city_info: Optional[CityInfo],
  ) -> List[CityPlayer]:
    players_by_key: Dict[str, CityPlayer] = {}

    if city_info is not None:
      for player in city_info.players:
        key = f"id:{player.user_id}" if player.user_id is not None else f"user:{player.username}"
        players_by_key[key] = player

    for player in city_repo.get_city_players(meta_id, city_name):
      if player.user_id is None:
        continue
      user_id = player.user_id
      profile = await try_refresh_profile(update, context, meta_id, city_name, user_id)
      dynamic_player = CityPlayer(
        user_id=user_id,
        display_name=build_display_name(None, profile, user_id),
        username=profile.get("username"),
      )
      players_by_key[f"id:{user_id}"] = dynamic_player

    return sorted(players_by_key.values(), key=lambda player: (player.display_name or "", player.username or ""))

  def city_counts(meta_id: str, city_name: str, city_info: Optional[CityInfo]) -> Tuple[int, int, int]:
    player_keys = {
      f"id:{player.user_id}" if player.user_id is not None else f"user:{player.username}"
      for player in city_repo.get_city_players(meta_id, city_name)
    }
    if city_info is not None:
      for player in city_info.players:
        key = f"id:{player.user_id}" if player.user_id is not None else f"user:{player.username}"
        player_keys.add(key)

    players_count = len(player_keys)
    clubs_count = len([club for club in city_info.clubs if club.visible]) if city_info is not None else 0
    ratings_count = len([rating for rating in city_info.ratings if rating.visible]) if city_info is not None else 0
    return players_count, clubs_count, ratings_count

  def build_city_list_markup(meta_id: str, page: int) -> Tuple[str, InlineKeyboardMarkup]:
    catalog = city_catalog.load(meta_id)
    city_names = sorted(set(city_repo.get_city_names(meta_id)) | set(catalog.keys()))
    pages = total_pages(city_names, CITY_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    page_city_names = paginate_items(city_names, page, CITY_PAGE_SIZE)

    keyboard = []
    for city_name in page_city_names:
      users_count = len(city_repo.get_city_players(meta_id, city_name))
      suffix = f" ({users_count})" if users_count else ""
      keyboard.append([InlineKeyboardButton(f"{city_name}{suffix}", callback_data=f"city:view:{page}:{city_name}")])

    navigation_row = []
    if page > 0:
      navigation_row.append(InlineKeyboardButton("⬅️", callback_data=f"cities:page:{page - 1}"))
    navigation_row.append(InlineKeyboardButton(f"{page + 1}/{pages}", callback_data="cities:noop"))
    if page + 1 < pages:
      navigation_row.append(InlineKeyboardButton("➡️", callback_data=f"cities:page:{page + 1}"))
    keyboard.append(navigation_row)
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="cities:close")])

    title = "<b>Города</b>\nВыберите город, чтобы открыть игроков, клубы и рейтинги."
    return title, InlineKeyboardMarkup(keyboard)

  def build_city_menu(meta_id: str, city_name: str, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    city_info = city_catalog.get_city(meta_id, city_name)
    players_count, clubs_count, ratings_count = city_counts(meta_id, city_name, city_info)

    lines = [f"<b>{escape(city_name)}</b>"]
    lines.append(f"Игроков: {players_count}")
    lines.append(f"Клубов: {clubs_count}")
    lines.append(f"Рейтингов: {ratings_count}")
    text = "\n".join(lines)

    keyboard = []
    keyboard.append([InlineKeyboardButton("Игроки", callback_data=f"city:players:0:{page}:{city_name}")])
    keyboard.append([InlineKeyboardButton("Клубы", callback_data=f"city:clubs:{page}:{city_name}")])
    keyboard.append([InlineKeyboardButton("Рейтинги", callback_data=f"city:ratings:{page}:{city_name}")])
    keyboard.append([
      InlineKeyboardButton("⬅️ Назад", callback_data=f"cities:page:{page}"),
      InlineKeyboardButton("❌ Закрыть", callback_data="cities:close"),
    ])
    return text, InlineKeyboardMarkup(keyboard)

  def build_links_markup(items, back_callback: str) -> InlineKeyboardMarkup:
    keyboard = []
    for item in items:
      keyboard.append([InlineKeyboardButton(item.title, url=item.url)])

    keyboard.append([
      InlineKeyboardButton("⬅️ Назад", callback_data=back_callback),
      InlineKeyboardButton("❌ Закрыть", callback_data="cities:close"),
    ])
    return InlineKeyboardMarkup(keyboard)

  async def build_players_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    meta_id: str,
    city_name: str,
    city_page: int,
    player_page: int,
  ) -> Tuple[str, InlineKeyboardMarkup]:
    city_info = city_catalog.get_city(meta_id, city_name)
    if city_info is not None and city_info.users_text:
      text = f"<b>{escape(city_name)}</b>\n{escape(city_info.users_text)}"
      keyboard = InlineKeyboardMarkup([
        [
          InlineKeyboardButton("⬅️ Назад", callback_data=f"city:view:{city_page}:{city_name}"),
          InlineKeyboardButton("❌ Закрыть", callback_data="cities:close"),
        ]
      ])
      return text, keyboard

    players = await resolve_city_players(update, context, meta_id, city_name, city_info)
    if not players:
      text = f"<b>{escape(city_name)}</b>\nНет данных об игроках."
      keyboard = InlineKeyboardMarkup([
        [
          InlineKeyboardButton("⬅️ Назад", callback_data=f"city:view:{city_page}:{city_name}"),
          InlineKeyboardButton("❌ Закрыть", callback_data="cities:close"),
        ]
      ])
      return text, keyboard

    pages = total_pages([player.display_name or "" for player in players], PLAYER_PAGE_SIZE)
    player_page = max(0, min(player_page, pages - 1))
    page_players = players[player_page * PLAYER_PAGE_SIZE : (player_page + 1) * PLAYER_PAGE_SIZE]

    lines = [f"<b>{escape(city_name)}</b>", "Игроки:"]
    keyboard = []
    for player in page_players:
      display_name = player.display_name or player.username or "Игрок"
      if player.user_id is not None:
        mention = f"<a href=\"tg://user?id={player.user_id}\">{escape(display_name)}</a>"
      else:
        mention = escape(display_name)

      if player.username:
        lines.append(f"• {mention} (@{escape(player.username)})")
      elif player.note:
        lines.append(f"• {mention} — {escape(player.note)}")
      else:
        lines.append(f"• {mention}")

      profile_url = build_profile_url(player)
      if profile_url:
        keyboard.append([InlineKeyboardButton(display_name, url=profile_url)])

    navigation_row = []
    if player_page > 0:
      navigation_row.append(
        InlineKeyboardButton("⬅️", callback_data=f"city:players:{player_page - 1}:{city_page}:{city_name}")
      )
    navigation_row.append(InlineKeyboardButton(f"{player_page + 1}/{pages}", callback_data="cities:noop"))
    if player_page + 1 < pages:
      navigation_row.append(
        InlineKeyboardButton("➡️", callback_data=f"city:players:{player_page + 1}:{city_page}:{city_name}")
      )
    keyboard.append(navigation_row)
    keyboard.append([
      InlineKeyboardButton("⬅️ Назад", callback_data=f"city:view:{city_page}:{city_name}"),
      InlineKeyboardButton("❌ Закрыть", callback_data="cities:close"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)

  def find_user_id_in_meta(meta_id: str, lookup_token: str) -> Optional[int]:
    player = city_repo.find_player(meta_id, lookup_token)
    if player is None:
      return None
    return player.user_id

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
    text, reply_markup = build_city_list_markup(meta_id, page=0)
    await send_or_edit(update, text, reply_markup)

  @check_chat_id
  async def users_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    if update.effective_message is None:
      return

    if not context.args:
      await update.effective_message.reply_text("Вы не указали город для вывода списка пользователей.")
      return

    city_name = " ".join(context.args).strip()
    text, reply_markup = build_city_menu(meta_id, city_name)
    await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

  @check_chat_id
  async def city_by_user(update: Update, context: ContextTypes.DEFAULT_TYPE, meta_id) -> None:
    user_tokens, error = parse_user_tokens(update, context)
    if error:
      await update.effective_message.reply_text(error.replace("пользователя.", "пользователя для получения города."))
      return

    for user_label, token in user_tokens.items():
      user_id = find_user_id_in_meta(meta_id, token)
      if user_id is None:
        await update.effective_message.reply_text(f"Пользователь {user_label} не числится в каком-либо городе.")
        continue

      city_name = city_repo.find_city_by_user_id(meta_id, user_id)
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
    city_repo.upsert_user_city(
      meta_id,
      new_city,
      user.id,
      display_name=user.full_name,
      username=user.username,
    )
    await update.effective_message.reply_text(f"Ваш город изменен на: {new_city}")

    if city_info is None or city_info.auto_show_members:
      text, reply_markup = build_city_menu(meta_id, new_city)
      await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

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
        "Вы не указали старое и новое имя города для переименования.\n"
        "Используйте запятую (,) в качестве разделителя."
      )
      return

    old_city, new_city = [part.strip() for part in command_text.split(",", 1)]
    if not old_city or not new_city:
      await update.effective_message.reply_text("Вы не указали старое и/или новое имя города для переименования.")
      return
    if old_city.startswith("/") or new_city.startswith("/"):
      await update.effective_message.reply_text("Некорректное имя города. Имена городов не могут начинаться с '/'.")
      return

    if not city_repo.rename_city(meta_id, old_city, new_city):
      await update.effective_message.reply_text(f"Город '{old_city}' не найден в списке городов.")
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
      user_id = find_user_id_in_meta(meta_id, token)
      if user_id is None:
        await update.effective_message.reply_text(f"Пользователь {user_label} не числится в каком-либо городе.")
        continue

      city_name = city_repo.find_city_by_user_id(meta_id, user_id)
      if city_name is None:
        await update.effective_message.reply_text(f"Пользователь {user_label} не числится в каком-либо городе.")
        continue

      city_repo.remove_user_from_city(meta_id, city_name, user_id)
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

    await query.answer()
    data = query.data or ""

    if data == "cities:close":
      await query.message.delete()
      return
    if data == "cities:noop":
      return
    if data.startswith("cities:page:"):
      page = int(data.split(":", 2)[2])
      text, reply_markup = build_city_list_markup(meta_id, page)
      await send_or_edit(update, text, reply_markup)
      return

    if data.startswith("city:view:"):
      _, _, page, city_name = data.split(":", 3)
      text, reply_markup = build_city_menu(meta_id, city_name, int(page))
      await send_or_edit(update, text, reply_markup)
      return

    if data.startswith("city:clubs:"):
      _, _, page, city_name = data.split(":", 3)
      city_info = city_catalog.get_city(meta_id, city_name)
      items = [club for club in city_info.clubs if club.visible] if city_info is not None else []
      text = f"<b>{escape(city_name)}</b>\nКлубы города."
      if not items:
        text += "\nПока нет ссылок."
      reply_markup = build_links_markup(items, f"city:view:{page}:{city_name}")
      await send_or_edit(update, text, reply_markup)
      return

    if data.startswith("city:ratings:"):
      _, _, page, city_name = data.split(":", 3)
      city_info = city_catalog.get_city(meta_id, city_name)
      items = [rating for rating in city_info.ratings if rating.visible] if city_info is not None else []
      text = f"<b>{escape(city_name)}</b>\nРейтинги города."
      if not items:
        text += "\nПока нет ссылок."
      reply_markup = build_links_markup(items, f"city:view:{page}:{city_name}")
      await send_or_edit(update, text, reply_markup)
      return

    if data.startswith("city:players:"):
      _, _, player_page, city_page, city_name = data.split(":", 4)
      text, reply_markup = await build_players_view(
        update,
        context,
        meta_id,
        city_name,
        int(city_page),
        int(player_page),
      )
      await send_or_edit(update, text, reply_markup)

  dispatcher.add_handler(CommandHandler("cities", cities))
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
