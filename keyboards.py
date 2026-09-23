from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def approval_keyboard(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"approve_user:{user_id}")
    builder.button(text="❌ Rad etish", callback_data=f"reject_user:{user_id}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_invoice_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ To'g'ri", callback_data="invoice_confirm")
    builder.button(text="✏️ Xato, qayta kiritish", callback_data="invoice_edit")
    builder.adjust(1)
    return builder.as_markup()


def duplicate_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Ha, bu men yuborgan edim", callback_data="dup_same")
    builder.button(text="Yo'q, bu boshqa hujjat", callback_data="dup_different")
    builder.adjust(1)
    return builder.as_markup()


def edit_field_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    fields = [
        ("Hujjat №", "edit_field:invoice_number"),
        ("Sana", "edit_field:date"),
        ("Xaridor", "edit_field:customer"),
        ("Agent", "edit_field:sales_agent"),
        ("Tovarlar ro'yxati", "edit_field:items"),
        ("Jami summa", "edit_field:total_sum"),
    ]
    for text, cb in fields:
        builder.button(text=text, callback_data=cb)
    builder.adjust(2)
    return builder.as_markup()
