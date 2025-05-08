from aiogram.fsm.state import StatesGroup, State


class StateUserActions(StatesGroup):
    listen = State()
