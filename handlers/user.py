import logging
from datetime import datetime, date as date_type

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import ADMIN_IDS
from database.db import get_session
from database.models import (
    TelegramUser, UserStatus, Supplier, Customer, SalesAgent, Expediter,
    Product, Invoice, InvoiceItem, InvoiceDuplicate, DuplicateDecision,
)
from ocr.gemini_ocr import recognize_invoice, OCRError
from states import Registration, InvoiceFlow
from keyboards import (
    approval_keyboard, confirm_invoice_keyboard, duplicate_keyboard, edit_field_keyboard,
)

router = Router()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    async with get_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

    if user is None:
        await message.answer(
            "Assalomu alaykum! Botdan foydalanish uchun avval ro'yxatdan o'tishingiz kerak.\n\n"
            "Ism-Familyangizni to'liq kiriting:"
        )
        await state.set_state(Registration.waiting_full_name)
        return

    if user.status == UserStatus.approved:
        await message.answer(
            "Xush kelibsiz! Накладная (chek) rasmini yuboring — men uni tahlil qilib beraman."
        )
        await state.set_state(InvoiceFlow.waiting_photo)
    elif user.status == UserStatus.pending:
        await message.answer("So'rovingiz hali admin tomonidan ko'rib chiqilmoqda. Iltimos, kuting.")
    else:
        await message.answer("Kechirasiz, so'rovingiz rad etilgan. Admin bilan bog'laning.")


@router.message(Registration.waiting_full_name)
async def reg_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer("JSHSHIR (shaxsni tasdiqlovchi ID) raqamingizni kiriting:")
    await state.set_state(Registration.waiting_id_number)


@router.message(Registration.waiting_id_number)
async def reg_id_number(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    full_name = data["full_name"]
    id_number = message.text.strip()

    async with get_session() as session:
        user = TelegramUser(
            telegram_id=message.from_user.id,
            full_name=full_name,
            id_number=id_number,
            status=UserStatus.pending,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    await message.answer(
        "Rahmat! So'rovingiz adminlarga yuborildi. Tasdiqlangach xabar beramiz."
    )
    await state.clear()

    text = (
        f"🆕 Yangi foydalanuvchi so'rovi:\n\n"
        f"Ism-Familiya: {full_name}\n"
        f"ID raqam: {id_number}\n"
        f"Telegram ID: {message.from_user.id}\n"
        f"Username: @{message.from_user.username or '—'}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=approval_keyboard(user.id))
        except Exception:
            logger.exception("Adminga xabar yuborib bo'lmadi: %s", admin_id)


# ---------------------------------------------------------- Накладная rasm
@router.message(F.photo)
async def receive_invoice_photo(message: Message, state: FSMContext, bot: Bot):
    async with get_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

    if user is None or user.status != UserStatus.approved:
        await message.answer("Sizda ruxsat yo'q. /start buyrug'ini bosing.")
        return

    processing_msg = await message.answer("🔍 Hujjat tahlil qilinmoqda, kuting...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)

    try:
        data = await recognize_invoice(file_bytes.read())
    except OCRError as e:
        await processing_msg.edit_text(
            f"❌ Rasmni o'qib bo'lmadi: {e}\nIltimos, yaqqolroq va to'g'ri holatdagi rasm yuboring."
        )
        return
    except Exception:
        logger.exception("OCR xatosi")
        await processing_msg.edit_text("❌ Kutilmagan xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return

    await state.update_data(invoice_data=data, photo_file_id=photo.file_id)
    await processing_msg.delete()
    await show_invoice_summary(message, state)


def format_invoice_summary(data: dict) -> str:
    items_text = "\n".join(
        f"{i+1}. {it.get('name')} — {it.get('quantity')} {it.get('unit') or ''} "
        f"× {it.get('unit_price')} = {it.get('line_total')}"
        for i, it in enumerate(data.get("items", []))
    )
    supplier = data.get("supplier") or {}
    customer = data.get("customer") or {}

    return (
        f"📄 Nakladnoy №{data.get('invoice_number')}\n"
        f"📅 Sana: {data.get('date')}\n"
        f"🏭 Postavshik: {supplier.get('name')}\n"
        f"🏬 Xaridor: {customer.get('name')}\n"
        f"👤 Agent: {data.get('sales_agent')}\n\n"
        f"Tovarlar:\n{items_text}\n\n"
        f"💰 Jami: {data.get('total_sum')} so'm"
    )


async def show_invoice_summary(message: Message, state: FSMContext):
    data = await state.get_data()
    text = format_invoice_summary(data["invoice_data"])
    await message.answer(text, reply_markup=confirm_invoice_keyboard())


# ---------------------------------------------------------------- Tasdiqlash
@router.callback_query(F.data == "invoice_confirm")
async def confirm_invoice(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    invoice_data = data["invoice_data"]
    invoice_number = invoice_data.get("invoice_number")

    async with get_session() as session:
        existing = None
        if invoice_number:
            result = await session.execute(
                select(Invoice).where(Invoice.invoice_number == invoice_number)
            )
            existing = result.scalar_one_or_none()

    if existing:
        result_user = None
        async with get_session() as session:
            result = await session.execute(
                select(TelegramUser).where(TelegramUser.id == existing.submitted_by)
            )
            result_user = result.scalar_one_or_none()
        sender_name = result_user.full_name if result_user else "noma'lum"
        await callback.message.edit_text(
            f"⚠️ Bu накладная (№{invoice_number}) DB'da allaqachon mavjud.\n"
            f"Uni {sender_name} avval yuborgan. Jami: {existing.total_sum} so'm.\n\n"
            f"Bu siz avval yuborgan hujjatmi?",
            reply_markup=duplicate_keyboard(),
        )
        return

    await save_invoice(callback, state)


async def save_invoice(callback: CallbackQuery, state: FSMContext, as_duplicate_variant: bool = False):
    data = await state.get_data()
    d = data["invoice_data"]
    photo_file_id = data["photo_file_id"]

    async with get_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one()

        supplier = await _get_or_create_supplier(session, d.get("supplier") or {})
        customer = await _get_or_create_customer(session, d.get("customer") or {})
        sales_agent = await _get_or_create_sales_agent(session, d.get("sales_agent"))
        expediter = await _get_or_create_expediter(session, d.get("expediter"))

        invoice_number = d.get("invoice_number") or f"NO-NUM-{datetime.utcnow().timestamp():.0f}"
        if as_duplicate_variant:
            invoice_number = f"{invoice_number}-DUP{int(datetime.utcnow().timestamp())}"

        try:
            invoice_date = (
                datetime.strptime(d["date"], "%Y-%m-%d").date()
                if d.get("date") else date_type.today()
            )
        except ValueError:
            invoice_date = date_type.today()

        invoice = Invoice(
            invoice_number=invoice_number,
            date=invoice_date,
            supplier=supplier,
            customer=customer,
            sales_agent=sales_agent,
            expediter=expediter,
            submitted_by=user.id,
            total_qty=d.get("total_qty"),
            total_sum=d.get("total_sum") or 0,
            discount_sum=d.get("discount_sum") or 0,
            photo_file_id=photo_file_id,
        )
        session.add(invoice)
        await session.flush()

        for it in d.get("items", []):
            product = await _get_or_create_product(session, it)
            session.add(InvoiceItem(
                invoice_id=invoice.id,
                product_id=product.id,
                quantity=it.get("quantity") or 0,
                unit_price=it.get("unit_price") or 0,
                line_total=it.get("line_total") or 0,
            ))

        await session.commit()

    await callback.message.edit_text(
        f"✅ Накладная №{invoice_number} muvaffaqiyatli saqlandi.\n"
        f"Yana hujjat yuborish uchun rasm jo'nating."
    )
    await state.set_state(InvoiceFlow.waiting_photo)


@router.callback_query(F.data == "dup_same")
async def duplicate_same(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    invoice_number = data["invoice_data"].get("invoice_number")

    async with get_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one()
        result = await session.execute(
            select(Invoice).where(Invoice.invoice_number == invoice_number)
        )
        invoice = result.scalar_one_or_none()
        if invoice:
            session.add(InvoiceDuplicate(
                invoice_id=invoice.id,
                submitted_by=user.id,
                decision=DuplicateDecision.same,
            ))
            await session.commit()

    await callback.message.edit_text("Tushunarli, hujjat qayta saqlanmadi. Rahmat!")
    await state.set_state(InvoiceFlow.waiting_photo)


@router.callback_query(F.data == "dup_different")
async def duplicate_different(callback: CallbackQuery, state: FSMContext):
    await save_invoice(callback, state, as_duplicate_variant=True)


# ---------------------------------------------------------------- Tahrirlash
@router.callback_query(F.data == "invoice_edit")
async def edit_invoice(callback: CallbackQuery):
    await callback.message.edit_text(
        "Qaysi maydonni to'g'rilaymiz?", reply_markup=edit_field_keyboard()
    )


@router.callback_query(F.data.startswith("edit_field:"))
async def edit_field_chosen(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":", 1)[1]
    await state.update_data(editing_field=field)
    await state.set_state(InvoiceFlow.waiting_edit_value)

    hints = {
        "invoice_number": "Yangi hujjat raqamini kiriting:",
        "date": "Sanani YYYY-MM-DD formatida kiriting (masalan 2026-05-15):",
        "customer": "To'g'ri xaridor nomini kiriting:",
        "sales_agent": "To'g'ri agent ismini kiriting:",
        "total_sum": "To'g'ri jami summani kiriting (faqat raqam):",
        "items": "Tovarlar ro'yxatini har bir qatorda 'kod;nomi;miqdor;narx' formatida yuboring:",
    }
    await callback.message.edit_text(hints.get(field, "Yangi qiymatni kiriting:"))


@router.message(InvoiceFlow.waiting_edit_value)
async def edit_value_received(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["editing_field"]
    invoice_data = data["invoice_data"]

    if field == "customer":
        invoice_data.setdefault("customer", {})["name"] = message.text.strip()
    elif field == "sales_agent":
        invoice_data["sales_agent"] = message.text.strip()
    elif field == "total_sum":
        try:
            invoice_data["total_sum"] = float(message.text.replace(",", ".").strip())
        except ValueError:
            await message.answer("Raqam noto'g'ri, qaytadan kiriting:")
            return
    elif field == "items":
        items = []
        for line in message.text.strip().splitlines():
            parts = [p.strip() for p in line.split(";")]
            if len(parts) != 4:
                await message.answer(
                    "Format noto'g'ri. Har bir qator: kod;nomi;miqdor;narx. Qaytadan yuboring:"
                )
                return
            code, name, qty, price = parts
            try:
                qty_f, price_f = float(qty), float(price)
            except ValueError:
                await message.answer("Miqdor/narx raqam bo'lishi kerak. Qaytadan yuboring:")
                return
            items.append({
                "code": code, "name": name, "unit": None,
                "quantity": qty_f, "unit_price": price_f, "line_total": qty_f * price_f,
            })
        invoice_data["items"] = items
    else:
        invoice_data[field] = message.text.strip()

    await state.update_data(invoice_data=invoice_data)
    await state.set_state(InvoiceFlow.waiting_photo)
    await message.answer("Yangilandi ✅")
    await show_invoice_summary(message, state)


# ---------------------------------------------------------------- Helperlar
async def _get_or_create_supplier(session, d: dict) -> Supplier:
    name = d.get("name") or "Noma'lum postavshik"
    result = await session.execute(select(Supplier).where(Supplier.name == name))
    obj = result.scalar_one_or_none()
    if obj is None:
        obj = Supplier(name=name, inn=d.get("inn"), address=d.get("address"), phone=d.get("phone"))
        session.add(obj)
        await session.flush()
    return obj


async def _get_or_create_customer(session, d: dict) -> Customer:
    name = d.get("name") or "Noma'lum xaridor"
    client_code = d.get("client_code")
    obj = None
    if client_code:
        result = await session.execute(select(Customer).where(Customer.client_code == client_code))
        obj = result.scalar_one_or_none()
    if obj is None:
        result = await session.execute(select(Customer).where(Customer.name == name))
        obj = result.scalar_one_or_none()
    if obj is None:
        obj = Customer(name=name, address=d.get("address"), inn=d.get("inn"), client_code=client_code)
        session.add(obj)
        await session.flush()
    return obj


async def _get_or_create_sales_agent(session, name: str | None) -> SalesAgent | None:
    if not name:
        return None
    result = await session.execute(select(SalesAgent).where(SalesAgent.full_name == name))
    obj = result.scalar_one_or_none()
    if obj is None:
        obj = SalesAgent(full_name=name)
        session.add(obj)
        await session.flush()
    return obj


async def _get_or_create_expediter(session, name: str | None) -> Expediter | None:
    if not name:
        return None
    result = await session.execute(select(Expediter).where(Expediter.full_name == name))
    obj = result.scalar_one_or_none()
    if obj is None:
        obj = Expediter(full_name=name)
        session.add(obj)
        await session.flush()
    return obj


async def _get_or_create_product(session, it: dict) -> Product:
    code = it.get("code") or it.get("name")
    result = await session.execute(select(Product).where(Product.code == code))
    obj = result.scalar_one_or_none()
    if obj is None:
        obj = Product(code=code, name=it.get("name") or code, unit=it.get("unit"))
        session.add(obj)
        await session.flush()
    return obj
