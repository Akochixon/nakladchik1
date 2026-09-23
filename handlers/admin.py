import csv
import io
import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from sqlalchemy import select, func

from config import ADMIN_IDS
from database.db import get_session
from database.models import TelegramUser, UserStatus, Invoice, InvoiceItem

router = Router()
logger = logging.getLogger(__name__)


def admin_only(handler):
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        if user_id not in ADMIN_IDS:
            if isinstance(event, CallbackQuery):
                await event.answer("Sizda ruxsat yo'q.", show_alert=True)
            else:
                await event.answer("Sizda ruxsat yo'q.")
            return
        return await handler(event, *args, **kwargs)
    return wrapper


@router.callback_query(F.data.startswith("approve_user:"))
@admin_only
async def approve_user(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split(":", 1)[1])
    async with get_session() as session:
        result = await session.execute(select(TelegramUser).where(TelegramUser.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return
        user.status = UserStatus.approved
        user.approved_by = callback.from_user.id
        user.approved_at = datetime.utcnow()
        await session.commit()
        telegram_id, full_name = user.telegram_id, user.full_name

    await callback.message.edit_text(f"✅ {full_name} tasdiqlandi.")
    try:
        await bot.send_message(
            telegram_id,
            "✅ So'rovingiz tasdiqlandi! Накладная rasmini yuborishingiz mumkin.",
        )
    except Exception:
        logger.exception("Foydalanuvchiga xabar yuborib bo'lmadi")


@router.callback_query(F.data.startswith("reject_user:"))
@admin_only
async def reject_user(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split(":", 1)[1])
    async with get_session() as session:
        result = await session.execute(select(TelegramUser).where(TelegramUser.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return
        user.status = UserStatus.rejected
        await session.commit()
        telegram_id, full_name = user.telegram_id, user.full_name

    await callback.message.edit_text(f"❌ {full_name} rad etildi.")
    try:
        await bot.send_message(telegram_id, "❌ So'rovingiz rad etildi.")
    except Exception:
        logger.exception("Foydalanuvchiga xabar yuborib bo'lmadi")


@router.message(Command("pending"))
@admin_only
async def list_pending(message: Message):
    async with get_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.status == UserStatus.pending)
        )
        users = result.scalars().all()

    if not users:
        await message.answer("Kutilayotgan so'rovlar yo'q.")
        return

    text = "\n".join(f"• {u.full_name} (ID: {u.id_number})" for u in users)
    await message.answer(f"Kutilayotgan so'rovlar:\n{text}")


@router.message(Command("stats"))
@admin_only
async def stats(message: Message):
    async with get_session() as session:
        total_invoices = await session.scalar(select(func.count(Invoice.id)))
        total_sum = await session.scalar(select(func.coalesce(func.sum(Invoice.total_sum), 0)))
        total_users = await session.scalar(
            select(func.count(TelegramUser.id)).where(TelegramUser.status == UserStatus.approved)
        )

    await message.answer(
        f"📊 Statistika:\n\n"
        f"Jami накладнойлар: {total_invoices}\n"
        f"Jami summa: {total_sum:,.2f} so'm\n"
        f"Faol agentlar: {total_users}"
    )


@router.message(Command("export"))
@admin_only
async def export_csv(message: Message):
    async with get_session() as session:
        result = await session.execute(
            select(Invoice).order_by(Invoice.date)
        )
        invoices = result.scalars().unique().all()

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(["Hujjat №", "Sana", "Postavshik", "Xaridor", "Agent", "Jami summa"])
        for inv in invoices:
            await session.refresh(inv, attribute_names=["supplier", "customer", "sales_agent"])
            writer.writerow([
                inv.invoice_number,
                inv.date.isoformat(),
                inv.supplier.name if inv.supplier else "",
                inv.customer.name if inv.customer else "",
                inv.sales_agent.full_name if inv.sales_agent else "",
                inv.total_sum,
            ])

    file_bytes = buf.getvalue().encode("utf-8-sig")
    await message.answer_document(
        BufferedInputFile(file_bytes, filename=f"invoices_{datetime.utcnow().date()}.csv"),
        caption="📄 Накладнойлар eksporti",
    )
