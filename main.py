import logging

from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config import ADMIN_USERNAME, CITY_CONTEXTS_DIR, LINKS_FILE, load_allowed_chats, load_token
from handlers.city_handlers import register_city_handlers
from handlers.common import make_check_chat_id
from handlers.days_handlers import register_days_handlers
from handlers.hand_handlers import register_hand_handlers
from handlers.links_handlers import register_links_handlers
from services.city_catalog_service import CityCatalog
from services.city_service import CityRepository


logging.basicConfig(
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
  if update.effective_message is None:
    return

  help_text = (
    "Список доступных команд (команды связанные с городами работают не во всех чатах):\n"
    "/help - Вывести список команд\n"
    "/cities - Открыть список городов\n"
    "<code>/users_from_city город</code> - Открыть меню города\n"
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
  await update.effective_message.reply_text(help_text, parse_mode="HTML")


async def chat_info_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
  if update.effective_message is None or update.effective_chat is None:
    return

  chat = update.effective_chat
  thread_id = update.effective_message.message_thread_id
  lines = [
    f"chat_id: <code>{chat.id}</code>",
    f"type: <code>{chat.type}</code>",
  ]
  if chat.title:
    lines.append(f"title: <code>{chat.title}</code>")
  if thread_id is not None:
    lines.append(f"thread_id: <code>{thread_id}</code>")

  await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


async def post_init(application) -> None:
  await application.bot.set_my_commands([
    BotCommand("help", "Список команд"),
    BotCommand("cities", "Список городов"),
    BotCommand("links", "Полезные ссылки"),
    BotCommand("this_week_poll", "Опрос по текущей неделе"),
    BotCommand("next_week_poll", "Опрос по следующей неделе"),
  ])


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
  logger.exception("Unhandled error while processing update %s", update, exc_info=context.error)


def main() -> None:
  token = load_token()
  city_catalog = CityCatalog(CITY_CONTEXTS_DIR)
  city_repo = CityRepository(city_catalog)
  allowed_chats = load_allowed_chats()
  check_chat_id = make_check_chat_id(city_repo, allowed_chats)

  application = ApplicationBuilder().token(token).post_init(post_init).job_queue(None).build()
  application.add_handler(CommandHandler("help", help_command))
  application.add_handler(CommandHandler("chat_info", chat_info_command))
  register_city_handlers(application, city_repo, city_catalog, check_chat_id, ADMIN_USERNAME)
  register_links_handlers(application, LINKS_FILE)
  register_hand_handlers(application)
  register_days_handlers(application)
  application.add_error_handler(error_handler)
  application.run_polling()


if __name__ == "__main__":
  main()
