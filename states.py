from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_full_name = State()
    waiting_id_number = State()


class InvoiceFlow(StatesGroup):
    waiting_photo = State()
    waiting_edit_value = State()
