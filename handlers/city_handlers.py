from telegram import ChatMember, Update
from telegram.ext import CallbackContext, CommandHandler


def register_city_handlers(dispatcher, city_repo, check_chat_id, admin_username):
  def is_admin(update: Update) -> bool:
    user = update.effective_user
    return (
      update.effective_chat.get_member(user.id).status in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR]
      or user.username == admin_username
    )

  def parse_user_mentions(update: Update):
    command_parts = update.message.text.strip().split(None, 1)
    if len(command_parts) < 2:
      return None, "Вы не указали пользователя."

    mentions = update.message.entities or []
    user_ids = {}

    for mention in mentions:
      if mention.type == "mention":
        user_mention = update.message.text[mention.offset + 1 : mention.offset + mention.length].lower()
        user_ids[user_mention] = user_mention
      elif mention.type == "text_mention":
        user_mention = update.message.text[mention.offset : mention.offset + mention.length]
        user_ids[user_mention] = f"ID:{mention.user.id}"

    if len(command_parts) == 2 and not any(m.type in ["mention", "text_mention"] for m in mentions):
      if len(command_parts[1].split()) == 1:
        user_mention = command_parts[1].strip().lower()
        user_ids[user_mention] = user_mention
      else:
        return None, (
          "Вы неправильно используете команду.\n"
          "Укажите один юзернейм или используйте текст с упоминаниями пользователей (можно нескольких).\n"
          "Для пользователей без юзернеймов поддерживается упоминание по ссылке."
        )

    return user_ids, None

  @check_chat_id
  def cities(update: Update, _: CallbackContext, meta_id) -> None:
    users_cities = city_repo.get_chat_data(meta_id).keys()
    if not users_cities:
      update.message.reply_text("Нет данных о городах и пользователях.")
      return

    cities_list = "\n".join(sorted(users_cities))
    update.message.reply_text(f"Список городов с пользователями в маджонговых чатах:\n{cities_list}")

  @check_chat_id
  def users_from_city(update: Update, context: CallbackContext, meta_id) -> None:
    command_parts = update.message.text.strip().split(None, 1)
    if len(command_parts) < 2:
      update.message.reply_text("Вы не указали город для вывода списка пользователей.")
      return

    city = command_parts[1].strip()
    chat_data = city_repo.get_chat_data(meta_id)
    users_ids = chat_data.get(city, [])

    if city == "Видное":
      update.message.reply_text(
        "Единственный пользователь из этого города - "
        "@shimmerko - занимает всё доступное место в городе."
      )
      return

    if not users_ids:
      update.message.reply_text(f"В маджонговых чатах нет данных о городе {city} или в нем нет пользователей.")
      return

    mention_list = []
    for user_id in users_ids:
      try:
        member = update.effective_chat.get_member(user_id)
        user = member.user
        name = f"{user.first_name} {user.last_name}" if user.last_name else user.first_name
        if user.username:
          mention_list.append(f"<a href=\"tg://user?id={user.id}\">{name}</a> (@{user.username})")
        else:
          mention_list.append(f"<a href=\"tg://user?id={user.id}\">{name}</a>")
      except Exception:
        mention_list.append(f"<a href=\"tg://user?id={user_id}\">ID:{user_id}</a>")

    users_list = "\n".join(mention_list)
    context.bot.send_message(
      chat_id=update.effective_message.chat_id,
      text=f"Пользователи из города {city}:\n{users_list}",
      parse_mode="HTML",
      disable_notification=True,
    )

  @check_chat_id
  def city_by_user(update: Update, _: CallbackContext, meta_id) -> None:
    user_ids, error = parse_user_mentions(update)
    if error:
      update.message.reply_text(error.replace("пользователя.", "пользователя для получения города."))
      return

    chat_data = city_repo.get_chat_data(meta_id)
    for user_id in user_ids:
      city = next(
        (
          city_name
          for city_name, users in chat_data.items()
          if user_ids[user_id]
          in [
            update.effective_message.chat.get_member(uid).user.username
            if update.effective_message.chat.get_member(uid).user.username
            else f"ID:{uid}"
            for uid in users
          ]
        ),
        None,
      )
      if city:
        update.message.reply_text(f"Город, привязанный к пользователю {user_id}: {city}")
      else:
        update.message.reply_text(f"Пользователь {user_id} не числится в каком-либо городе.")

  @check_chat_id
  def my_city(update: Update, context: CallbackContext, meta_id) -> None:
    user = update.effective_user
    command_parts = update.message.text.strip().split(None, 1)
    if len(command_parts) < 2:
      update.message.reply_text("Вы не указали новый город для смены.")
      return

    new_city = command_parts[1].strip()
    if new_city.startswith("/"):
      update.message.reply_text("Некорректное имя города. Город не может начинаться с '/'")
      return
    if new_city == "Видное":
      update.message.reply_text("К сожалению в этом городе слишком тесно - вы не поместитесь =(")
      return

    chat_data = city_repo.get_chat_data(meta_id)
    if not chat_data:
      chat_data = {new_city: [user.id]}
    else:
      old_city = next((city for city, users in chat_data.items() if user.id in users), None)
      if old_city:
        chat_data[old_city].remove(user.id)
        if not chat_data[old_city]:
          del chat_data[old_city]

      if new_city not in chat_data:
        chat_data[new_city] = []
      chat_data[new_city].append(user.id)

    city_repo.set_chat_data(meta_id, chat_data)
    update.message.reply_text(f"Ваш город изменен на: {new_city}")

    if new_city not in ["Москва", "Санкт-Петербург"]:
      users_from_city(update, context)

  @check_chat_id
  def leave_city(update: Update, _: CallbackContext, meta_id) -> None:
    user = update.effective_user
    chat_data = city_repo.get_chat_data(meta_id)
    city = next((city_name for city_name, users in chat_data.items() if user.id in users), None)
    if not city:
      update.message.reply_text("Вы не числитесь в каком-либо городе.")
      return

    city_repo.remove_user_from_city(meta_id, city, user.id)
    update.message.reply_text(f"Вы удалены из города {city}.")

  @check_chat_id
  def rename_city(update: Update, _: CallbackContext, meta_id) -> None:
    if not is_admin(update):
      update.message.reply_text("Вы не являетесь администратором.")
      return

    if len(update.message.text.split()) < 2:
      update.message.reply_text(
        "Вы не указали старое и новое имя города для переименования.\n"
        "Используйте запятую (,) в качестве разделителя."
      )
      return

    command_text = update.message.text.split(None, 1)[1].strip()
    if "," not in command_text:
      update.message.reply_text(
        "Вы не указали старое и новое имя города для переименования.\n"
        "Используйте запятую (,) в качестве разделителя."
      )
      return

    arg_cities = command_text.split(",")
    if len(arg_cities) != 2:
      update.message.reply_text("Вы должны указать ровно два города для переименования.")
      return

    old_city, new_city = arg_cities[0].strip(), arg_cities[1].strip()
    if not old_city or not new_city:
      update.message.reply_text("Вы не указали старое и/или новое имя города для переименования.")
      return
    if old_city.startswith("/") or new_city.startswith("/"):
      update.message.reply_text("Некорректное имя города. Имена городов не могут начинаться с '/'")
      return

    chat_data = city_repo.get_chat_data(meta_id)
    if old_city not in chat_data:
      update.message.reply_text(f"Город '{old_city}' не найден в списке городов.")
      return

    chat_data[new_city] = chat_data.get(new_city, []) + chat_data[old_city]
    del chat_data[old_city]
    city_repo.set_chat_data(meta_id, chat_data)
    update.message.reply_text(f"Город '{old_city}' переименован в '{new_city}'.")

  @check_chat_id
  def remove_user(update: Update, _: CallbackContext, meta_id) -> None:
    if not is_admin(update):
      update.message.reply_text("Вы не являетесь администратором.")
      return

    user_ids, error = parse_user_mentions(update)
    if error:
      update.message.reply_text(error.replace("пользователя.", "пользователя для удаления."))
      return

    chat_data = city_repo.get_chat_data(meta_id)
    for user_id in user_ids:
      city = next(
        (
          city_name
          for city_name, users in chat_data.items()
          if user_ids[user_id]
          in [
            update.effective_message.chat.get_member(uid).user.username
            if update.effective_message.chat.get_member(uid).user.username
            else f"ID:{uid}"
            for uid in users
          ]
        ),
        None,
      )
      if not city:
        update.message.reply_text(f"Пользователь {user_id} не числится в каком-либо городе.")
        continue

      if user_ids[user_id].startswith("ID:"):
        remove_id = int(user_ids[user_id][3:])
      else:
        remove_id = None
      for id_temp in chat_data[city]:
        user = update.effective_message.chat.get_member(id_temp).user
        if user.username == user_ids[user_id]:
          remove_id = id_temp
          break

      if remove_id is not None:
        city_repo.remove_user_from_city(meta_id, city, remove_id)
        update.message.reply_text(f"Пользователь {user_id} удален из города {city}")

  @check_chat_id
  def remove_city(update: Update, _: CallbackContext, meta_id) -> None:
    if not is_admin(update):
      update.message.reply_text("Вы не являетесь администратором.")
      return

    command_parts = update.message.text.strip().split(None, 1)
    if len(command_parts) < 2:
      update.message.reply_text("Вы не указали город для удаления.")
      return

    city = command_parts[1].strip()
    chat_data = city_repo.get_chat_data(meta_id)
    if city in chat_data:
      del chat_data[city]
      city_repo.set_chat_data(meta_id, chat_data)
      update.message.reply_text(f"Город {city} удален из списка городов.")

  @check_chat_id
  def debug(update: Update, _: CallbackContext, meta_id) -> None:
    user = update.effective_user
    if user.username != admin_username:
      update.message.reply_text("Вы не являетесь администратором.")
      return
    update.message.reply_text(f"Структура city_users:\n{city_repo.get_chat_data(meta_id)}")

  def debug_all(update: Update, _: CallbackContext) -> None:
    user = update.effective_user
    if user.username != admin_username:
      update.message.reply_text("Вы не являетесь администратором.")
      return
    update.message.reply_text(f"Структура city_users:\n{city_repo.get_all()}")

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
