import logging
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, Updater

from config import ADMIN_USERNAME, ALLOWED_CHATS, DATA_FILE, LINKS_FILE, load_token
from handlers.city_handlers import register_city_handlers
from handlers.common import make_check_chat_id
from handlers.days_handlers import register_days_handlers
from handlers.hand_handlers import register_hand_handlers
from handlers.links_handlers import register_links_handlers
from services.city_service import CityRepository

# Установка уровня логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


# Справка по командам
def help(update: Update, _: CallbackContext) -> None:
  help_text = (
    "Список доступных команд (команды связанные с городами работают не во всех чатах):\n"
    "/help - Вывести список команд\n"
    "/cities - Вывести список городов с пользователями\n"
    "<code>/users_from_city город</code> - Вывести список пользователей из указанного города\n"
    # "<code>/city_by_user юзернейм</code> - Получить город по упоминанию пользователя\n"
    "<code>/my_city город</code> - Установить/изменить свой город\n"
    "<code>/leave_city</code> - Удалить себя из текущего города\n"
    "/links - Полезные ссылки\n"
    "/this_week_poll - Опрос по дням на эту неделю\n"
    "/next_week_poll - Опрос по дням на следующую неделю\n"
    "/hand - Сделать изображение руки. Формат:\n"
    "<code>19m19p19s1234z567z_0m</code> (пример - кокуши с 13-сторонним ожиданием и акадорой взятой со стены),\n"
    "для пробелов в руке используйте нижнее подчёркивание - <code>_</code>,\n"
    "для тайла рубашкой используйте заглавную латинскую i - <code>I</code>,\n"
    "для повёрнутого тайла используйте дефис перед ним - <code>-1m</code>,\n"
    "два повёрнутых подряд стакаются как в апгрейде пона до кана\n"
  )
  update.message.reply_text(help_text, parse_mode='html')


def main() -> None:
  token = load_token()
  updater = Updater(token)
  city_repo = CityRepository(DATA_FILE)
  check_chat_id = make_check_chat_id(city_repo, ALLOWED_CHATS)

  dispatcher = updater.dispatcher
  dispatcher.add_handler(CommandHandler("help", help))
  register_city_handlers(dispatcher, city_repo, check_chat_id, ADMIN_USERNAME)
  register_links_handlers(dispatcher, LINKS_FILE)
  register_hand_handlers(dispatcher)
  register_days_handlers(dispatcher)

  updater.start_polling()
  updater.idle()
  city_repo.save()


if __name__ == '__main__':
  main()
