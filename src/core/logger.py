import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from src.core.paths import LOGS_DIR

# Настройка основного логгера
os.makedirs(LOGS_DIR, exist_ok=True)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Минимальный уровень логирования

# Формат сообщений
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Хендлер для записи в файл с ротацией
file_handler = RotatingFileHandler(
    filename=os.path.join(LOGS_DIR, "app.log"),
    maxBytes=1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setLevel(logging.DEBUG)  # Запись всех сообщений от DEBUG и выше
file_handler.setFormatter(formatter)

# Хендлер для вывода в консоль
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)  # Только INFO и выше
console_handler.setFormatter(formatter)

# Добавление хендлеров в логгер
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# def setup_logger(name, log_file="app.log", level=logging.INFO):
#     """To setup as many loggers as you want"""
#
#     logger = logging.getLogger(name)
#
#     file_handler = RotatingFileHandler(
#         filename=os.path.join(LOGS_DIR, log_file),
#         maxBytes=1024 * 1024,
#         backupCount=5,
#         encoding="utf-8",
#     )
#     file_handler.setLevel(logging.DEBUG)  # Запись всех сообщений от DEBUG и выше
#     file_handler.setFormatter(formatter)
#
#     # Хендлер для вывода в консоль
#     console_handler = logging.StreamHandler(sys.stdout)
#     console_handler.setLevel(level)  # Только INFO и выше
#     console_handler.setFormatter(formatter)
#
#     # Добавление хендлеров в логгер
#     logger.addHandler(file_handler)
#     logger.addHandler(console_handler)
#     return logger
