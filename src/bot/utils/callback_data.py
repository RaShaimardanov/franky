from aiogram.filters.callback_data import CallbackData


class UserSettingsCallback(CallbackData, prefix="settings"):
    show_role_name: bool
