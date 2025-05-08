import argparse
import asyncio

from src.bot.setup import setup_bot, setup_dispatcher
from src.core.logger import logger
from src.utils.parser import run_parser


def parse_args() -> argparse.Namespace:
    """Обработка аргументов командной строки."""
    parser = argparse.ArgumentParser(description="Френки-шоу бот")
    parser.add_argument("-p", "--parse", action="store_true", help="Запустить парсер")
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    """Основная точка входа в приложение."""
    if args.parse:
        await run_parser()
    bot = setup_bot()
    dp = setup_dispatcher()

    logger.info("Запуск бота...")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    try:
        logger.info("Инициализация бота...")
        asyncio.run(main(parse_args()))
    except KeyboardInterrupt:
        logger.info("Бот остановлен...")
    except Exception as e:
        logger.exception(f"Неизвестная ошибка: {str(e)}")
        raise
