class WebDriverError(Exception):
    """Исключение, связанное с ошибками веб-драйвера."""

    pass


class LinkProcessingError(Exception):
    """Исключение, связанное с ошибками обработки ссылок."""

    pass


class DatabaseError(Exception):
    """Исключение, связанное с ошибками работы с базой данных."""

    pass


class UpdateFieldError(DatabaseError):
    """Исключение, связанное с ошибкой обновления поля."""

    pass


class FileManagerError(Exception):
    """Исключение, связанное с ошибками управления файлами."""

    pass


class PageParsingError(Exception):
    """Исключение, связанное с ошибками парсинга страницы."""

    pass


class DownloadTimeoutError(Exception):
    """Исключение, связанное с истечением времени ожидания загрузки."""

    pass


class AudioServiceException(Exception):
    """Базовое исключение для ошибок сервиса AudioService()"""

    pass


class AudioFileNotFound(AudioServiceException):
    """Исключение возникает, когда аудиофайл не найден"""

    pass
