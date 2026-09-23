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


# ---------------------------------------------------------------- Diagnostika
@router.message(Command("myid"))
async def my_id(message: Message):
    """Har kim o'z Telegram ID raqamini va admin ekan-emasligini ko'rishi uchun."""
    is_admin = message.from_user.id in ADMIN_IDS

    admin_status = (
        "✅ Ha, siz adminsiz"
        if is_admin
        else "❌ Yo'q"
    )

    await message.answer(
        f"🆔 Sizning Telegram ID: <code>{message.from_user.id}</code>\n"
        f"👑 Admin holati: {admin_status}\n\n"
        f"Joriy ADMIN_IDS ro'yxatida {len(ADMIN_IDS)} ta ID bor."
    )


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "Sizda admin huquqi yo'q. O'z ID raqamingizni bilish uchun /myid ni bosing."
        )
        return

    await message.answer(
        "👑 <b>Admin rejimi</b>\n\n"
        "/pending — kutilayotgan so'rovlar\n"
        "/stats — statistika\n"
        "/export — накладнойларни CSV qilib eksport qilish\n\n"
        "Накладной yuborib, oddiy agent sifatida ishlash uchun /user buyrug'ini bosing."
    )


# ---------------------------------------------------------------- Tasdiqlash
@router.callback_query(F.data.startswith("approve_user:"))
async def approve_user(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

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
    await callback.answer()
    try:
        await bot.send_message(
            telegram_id,
            "✅ So'rovingiz tasdiqlandi! Накладная rasmini yuborishingiz mumkin.",
        )
    except Exception:
        logger.exception("Foydalanuvchiga xabar yuborib bo'lmadi")


@router.callback_query(F.data.startswith("reject_user:"))
async def reject_user(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

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
    await callback.answer()
    try:
        await bot.send_message(telegram_id, "❌ So'rovingiz rad etildi.")
    except Exception:
        logger.exception("Foydalanuvchiga xabar yuborib bo'lmadi")


@router.message(Command("pending"))
async def list_pending(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Sizda ruxsat yo'q.")
        return

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
async def stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Sizda ruxsat yo'q.")
        return

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
async def export_csv(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Sizda ruxsat yo'q.")
        return

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