from telegram import Update, ChatMember
from telegram.ext import Updater, CommandHandler, CallbackContext
import os
import json
import logging
import pip
pip.main(['install', 'python-telegram-bot==13.13'])

# Установка уровня логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Ваш токен бота, полученный от @BotFather
# TOKEN = os.environ['bot_token']
TOKEN = "5950642026:AAH3Gp6UTnA6ORplu8BSDivs_H8xtSb6PW0"

# Имя пользователя администратора
ADMIN_USERNAME = "xxldoctor"

# Глобальная переменная для хранения данных о городах и пользователях
DATA_FILE = "city_users.json"

# Список допустимых chat_id, где бот может быть использован
ALLOWED_CHATS = {"-1001078882316": "mahjong", "-1001182235196": "mahjong", "-1001167521254": "mahjong", "-840250661": "test", "-938606890": "test"}


# Загрузка данных из файла
def load_data_from_file():
  try:
    with open(DATA_FILE, "r") as file:
      data = json.load(file)
  except FileNotFoundError:
    data = {}

  # Преобразуем ключи в строки перед возвратом данных
  return {str(key): value for key, value in data.items()}


city_users = load_data_from_file()


# Сохранение данных в файл
def save_data_to_file(data):
  with open(DATA_FILE, "w") as file:
    json.dump({str(key): value for key, value in data.items()}, file)


# Декоратор для проверки chat_id
def check_chat_id(func):
  def wrapper(update, context):
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)  # Получаем айди пользователя

    # Проверяем, является ли чат личным
    if chat_id == user_id:
      # Чат личный, проверяем, есть ли пользователь в списках городов
      all_user_ids = [user_id for city_users in city_users.get('mahjong', {}).values() for user_id in city_users]
      if int(user_id) in all_user_ids:
        # Пользователь найден в списке городов, разрешаем выполнение команды
        return func(update, context, meta_id='mahjong')

      # Пользователь не найден в списках городов
      update.message.reply_text("Извините, но вы не числитесь в каком-либо городе. Для использования бота в личке выполните <code>/my_city город</code> в одном из маджонговых чатов.", parse_mode='html')
      return
      
    # Проверяем, что чат находится в списке разрешенных
    if chat_id not in ALLOWED_CHATS:
      update.message.reply_text("Извините, но эту команду можно использовать только в определенных чатах.")
      return
      
    # Возвращаем данные, которые могут быть использованы в функции команды
    return func(update, context, meta_id=ALLOWED_CHATS[chat_id])
  return wrapper


# Справка по командам
def help(update: Update, _: CallbackContext) -> None:
  help_text = (
    "Список доступных команд:\n"
    "/help - Вывести список команд\n"
    "/cities - Вывести список городов с пользователями\n"
    "<code>/users_from_city город</code> - Вывести список пользователей из указанного города\n"
    # "<code>/city_by_user юзернейм</code> - Получить город по упоминанию пользователя\n"
    "<code>/my_city город</code> - Установить/изменить свой город\n"
    "<code>/leave_city</code> - Удалить себя из текущего города\n"
    "/links - Полезные ссылки\n"
  )
  update.message.reply_text(help_text, parse_mode='html')


# Функция возвращающая список городов с пользователями
@check_chat_id
def cities(update: Update, _: CallbackContext, meta_id) -> None:

  # Получаем список городов для текущего чата
  users_cities = city_users.get(meta_id, {}).keys()

  if not users_cities:
    update.message.reply_text("Нет данных о городах и пользователях.")
    return

  cities_list = "\n".join(sorted(users_cities))
  update.message.reply_text(f"Список городов с пользователями в маджонговых чатах:\n{cities_list}")


# Функция для получения пользователей по городу
@check_chat_id
def users_from_city(update: Update, context: CallbackContext, meta_id) -> None:
  command_parts = update.message.text.strip().split(None, 1)

  if len(command_parts) < 2:
    update.message.reply_text("Вы не указали город для вывода списка пользователей.")
    return

  city = command_parts[1].strip()  # Удаляем лишние пробелы

  # Получаем список пользователей для указанного города в текущем чате
  chat_data = city_users.get(meta_id, {})
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

  # Список пользователей для упоминания
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
    except Exception as e:
      mention_list.append(f"<a href=\"tg://user?id={user_id}\">ID:{user_id}</a>")
  
  # Формируем строку с упоминаниями пользователей
  users_list = "\n".join(mention_list)
  
  # Отправляем сообщение без звукового уведомления о городе и списка пользователей
  message_text = f"Пользователи из города {city}:\n{users_list}"
  context.bot.send_message(
    chat_id=update.effective_message.chat_id,
    text=message_text,
    parse_mode='HTML',
    disable_notification=True
  )


# Функция для получения города по пользователю
@check_chat_id
def city_by_user(update: Update, _: CallbackContext, meta_id) -> None:
  command_parts = update.message.text.strip().split(None, 1)

  if len(command_parts) < 2:
    update.message.reply_text("Вы не указали пользователя для получения города.")
    return

  # Извлекаем упоминания пользователей из текста сообщения
  mentions = update.message.entities
  user_ids = {}

  for mention in mentions:
    if mention.type == "mention":
      user_mention = update.message.text[mention.offset + 1: mention.offset + mention.length].lower()
      user_ids[user_mention] = user_mention
    elif mention.type == "text_mention":
      user_mention = update.message.text[mention.offset: mention.offset + mention.length]
      user_ids[user_mention] = f"ID:{mention.user.id}"

  # Если указано только одно слово (не упоминание пользователя), используем его как user_mention
  if len(command_parts) == 2 and not any(mention.type in ["mention", "text_mention"] for mention in mentions):
    if len(command_parts[1].split()) == 1:
      user_mention = command_parts[1].strip().lower()
      user_ids[user_mention] = user_mention
    else:
      update.message.reply_text(
        "Вы неправильно используете команду.\n"
        "Укажите один юзернейм или используйте текст с упоминаниями пользователей (можно нескольких).\n"
        "Для пользователей без юзернеймов поддерживается упоминание по ссылке."
      )
      return

  # Получим данные о городах и пользователей для текущего чата
  chat_data = city_users.get(meta_id, {})

  for user_id in user_ids:
    # Найдем город, если пользователь с таким username или id существует в текущем чате
    city = next((city for city, users in chat_data.items() if user_ids[user_id] in [
      update.effective_message.chat.get_member(user_id).user.username 
      if update.effective_message.chat.get_member(user_id).user.username 
      else f"ID:{user_id}" for user_id in users]), None)

    if city:
      update.message.reply_text(f"Город, привязанный к пользователю {user_id}: {city}")
    else:
      update.message.reply_text(f"Пользователь {user_id} не числится в каком-либо городе.")


# Функция для изменения города пользователем
@check_chat_id
def my_city(update: Update, context: CallbackContext, meta_id) -> None:
  user = update.effective_user
  command_parts = update.message.text.strip().split(None, 1)

  if len(command_parts) < 2:
    update.message.reply_text("Вы не указали новый город для смены.")
    return

  new_city = command_parts[1].strip()  # Удаляем лишние пробелы

  if new_city.startswith('/'):
    update.message.reply_text("Некорректное имя города. Город не может начинаться с '/'")
    return

  if new_city == "Видное":
    update.message.reply_text("К сожалению в этом городе слишком тесно - вы не поместитесь =(")
    return

  # Получим данные о городах и пользователях для текущего чата
  chat_data = city_users.get(meta_id, {})

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

  # Сохраняем данные о городах и пользователях для текущего чата
  city_users[meta_id] = chat_data
  save_data_to_file(city_users)

  update.message.reply_text(f"Ваш город изменен на: {new_city}")
  if new_city not in ["Москва", "Санкт-Петербург"]:
    users_from_city(update, context)


# Функция для удаления пользователя из города
@check_chat_id
def leave_city(update: Update, _: CallbackContext, meta_id) -> None:
  user = update.effective_user

  # Получим данные о городах и пользователей для текущего чата
  chat_data = city_users.get(meta_id, {})

  city = next((city for city, users in chat_data.items() if user.id in users), None)

  if not city:
    update.message.reply_text("Вы не числитесь в каком-либо городе.")
    return

  remove_user_from_city(meta_id, city, user.id)
  update.message.reply_text(f"Вы удалены из города {city}.")

  # Сохраняем данные о городах и пользователях для текущего чата
  city_users[meta_id] = chat_data
  save_data_to_file(city_users)


# Функция для администратора для переименования города
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
    
  # Получаем текст команды (без самой команды /rename_city)
  command_text = update.message.text.split(None, 1)[1].strip()

  if ',' not in command_text:
    update.message.reply_text(
      "Вы не указали старое и новое имя города для переименования.\n"
      "Используйте запятую (,) в качестве разделителя."
    )
    return

  arg_cities = command_text.split(',')
  if len(arg_cities) != 2:
    update.message.reply_text("Вы должны указать ровно два города для переименования.")
    return

  old_city, new_city = arg_cities[0].strip(), arg_cities[1].strip()
  old_city, new_city = old_city.strip(), new_city.strip()

  if not old_city or not new_city:
    update.message.reply_text("Вы не указали старое и/или новое имя города для переименования.")
    return

  if old_city.startswith('/') or new_city.startswith('/'):
    update.message.reply_text("Некорректное имя города. Имена городов не могут начинаться с '/'")
    return

  # Получим данные о городах и пользователей для текущего чата
  chat_data = city_users.get(meta_id, {})

  if old_city not in chat_data:
    update.message.reply_text(f"Город '{old_city}' не найден в списке городов.")
    return

  # Объединим списки пользователей из старого и нового городов
  chat_data[new_city] = chat_data.get(new_city, []) + chat_data[old_city]
  del chat_data[old_city]
  update.message.reply_text(f"Город '{old_city}' переименован в '{new_city}'.")

  # Сохраняем данные о городах и пользователях для текущего чата
  city_users[meta_id] = chat_data
  save_data_to_file(city_users)


# Функция для администратора для удаления пользователя
@check_chat_id
def remove_user(update: Update, _: CallbackContext, meta_id) -> None:

  if not is_admin(update):
    update.message.reply_text("Вы не являетесь администратором.")
    return

  command_parts = update.message.text.strip().split(None, 1)

  if len(command_parts) < 2:
    update.message.reply_text("Вы не указали пользователя для удаления.")
    return

  # Извлекаем упоминания пользователей из текста сообщения
  mentions = update.message.entities
  user_ids = {}

  for mention in mentions:
    if mention.type == "mention":
      user_mention = update.message.text[mention.offset + 1: mention.offset + mention.length].lower()
      user_ids[user_mention] = user_mention
    elif mention.type == "text_mention":
      user_mention = update.message.text[mention.offset: mention.offset + mention.length]
      user_ids[user_mention] = f"ID:{mention.user.id}"

  # Если указано только одно слово (не упоминание пользователя), используем его как user_mention
  if len(command_parts) == 2 and not any(mention.type in ["mention", "text_mention"] for mention in mentions):
    if len(command_parts[1].split()) == 1:
      user_mention = command_parts[1].strip().lower()
      user_ids[user_mention] = user_mention
    else:
      update.message.reply_text(
        "Вы неправильно используете команду.\n"
        "Укажите один юзернейм или используйте текст с упоминаниями пользователей (можно нескольких).\n"
        "Для пользователей без юзернеймов поддерживается упоминание по ссылке."
      )
      return

  # Получим данные о городах и пользователей для текущего чата
  chat_data = city_users.get(meta_id, {})

  for user_id in user_ids:
    # Найдем город, если пользователь с таким username или id существует в текущем чате
    city = next((city for city, users in chat_data.items() if user_ids[user_id] in [
      update.effective_message.chat.get_member(user_id).user.username
      if update.effective_message.chat.get_member(user_id).user.username
      else f"ID:{user_id}" for user_id in users]), None)

    if city:  
      if user_ids[user_id].startswith("ID:"):
        remove_id = int(user_ids[user_id][3:])
      else:
        remove_id = None
      for id_temp in chat_data[city]:
        user = update.effective_message.chat.get_member(id_temp).user
        if user.username == user_ids[user_id]:
          remove_id = id_temp
          break
      remove_user_from_city(meta_id, city, remove_id)
      update.message.reply_text(f"Пользователь {user_id} удален из города {city}")
    else:
      update.message.reply_text(f"Пользователь {user_id} не числится в каком-либо городе.")

  # Сохраняем данные о городах и пользователях для текущего чата
  city_users[meta_id] = chat_data
  save_data_to_file(city_users)


# Функция для администратора для удаления города
@check_chat_id
def remove_city(update: Update, _: CallbackContext, meta_id) -> None:

  if not is_admin(update):
    update.message.reply_text("Вы не являетесь администратором.")
    return

  command_parts = update.message.text.strip().split(None, 1)

  if len(command_parts) < 2:
    update.message.reply_text("Вы не указали город для удаления.")
    return

  city = command_parts[1].strip()  # Удаляем лишние пробелы

  # Получим данные о городах и пользователей для текущего чата
  chat_data = city_users.get(meta_id, {})

  if city in chat_data:
    del chat_data[city]
    update.message.reply_text(f"Город {city} удален из списка городов.")

  # Сохраняем данные о городах и пользователей для текущего чата
  city_users[meta_id] = chat_data
  save_data_to_file(city_users)

# Отладка данных
@check_chat_id
def debug(update: Update, _: CallbackContext, meta_id) -> None:
  user = update.effective_user

  if user.username != ADMIN_USERNAME:
    update.message.reply_text("Вы не являетесь администратором.")
    return

  # Получим данные о городах и пользователей для текущего чата
  chat_data = city_users.get(meta_id, {})

  update.message.reply_text(f"Структура city_users:\n{chat_data}")


# Отладка данных
def debug_all(update: Update, _: CallbackContext) -> None:
  user = update.effective_user

  if user.username != ADMIN_USERNAME:
    update.message.reply_text("Вы не являетесь администратором.")
    return

  update.message.reply_text(f"Структура city_users:\n{city_users}")


# Вывод ссылок
def linksn(update: Update, _: CallbackContext) -> None:
  # Открываем файл с ссылками и читаем их в список
  with open("links.json", "r", encoding="utf-8") as file:
    links_list = json.load(file)

  links_text = "\n".join(links_list)

  # Отправляем список ссылок в чат
  update.message.reply_text(links_text, parse_mode='html', disable_web_page_preview=True)


# Вывод ссылок 2
def links(update: Update, _: CallbackContext) -> None:
  # Открываем файл с ссылками и читаем их в список
  with open("linksn.json", "r", encoding="utf-8") as file:
    data = json.load(file)

  message = "<b>Полезные ссылки:</b>\n"

  for section in data.get('sections', []):
    message += f"\n<b>{section['title']}</b>\n"
    for link in section.get('links', []):
        message += f" - {link}\n"

  # Отправляем список ссылок в чат
  update.message.reply_text(message, parse_mode='html', disable_web_page_preview=True)


# Проверка админправ
def is_admin(update):
  user = update.effective_user
  return (update.effective_chat.get_member(user.id).status in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR]
          or user.username == ADMIN_USERNAME)


# Удаление пользователя из города
def remove_user_from_city(meta_id, city, user_id):
  # Получим данные о городах и пользователях для указанного chat_id
  chat_data = city_users.get(meta_id, {})

  # Проверим, есть ли указанный город в данных
  if city not in chat_data:
    return False  # Город не найден, выходим с ошибкой

  # Получим список пользователей для указанного города
  users_ids = chat_data[city]

  # Проверим, есть ли указанный пользователь в списке пользователей города
  if user_id not in users_ids:
    return False  # Пользователь не найден в указанном городе, выходим с ошибкой

  # Удаляем пользователя из списка пользователей города
  users_ids.remove(user_id)

  # Если город стал пустым после удаления пользователя, удаляем его из списка городов
  if not chat_data[city]:
    del chat_data[city]

  # Сохраняем обновленные данные о городах и пользователях
  city_users[meta_id] = chat_data
  save_data_to_file(city_users)

  return True  # Успешно удалили пользователя из города


def main() -> None:
  updater = Updater(TOKEN)

  # Получение диспетчера для регистрации обработчиков
  dispatcher = updater.dispatcher
  dispatcher.add_handler(CommandHandler("help", help))
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
  dispatcher.add_handler(CommandHandler("links", links))
  dispatcher.add_handler(CommandHandler("linksn", linksn))

  # Запуск бота
  updater.start_polling()

  # Остановка бота при нажатии Ctrl+C
  updater.idle()

  # Сохранение данных в файл после остановки бота
  save_data_to_file(city_users)


if __name__ == '__main__':
  main()
