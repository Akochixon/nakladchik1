from datetime import datetime, date as date_type
from sqlalchemy import (
    BigInteger, String, Integer, Numeric, Date, DateTime,
    ForeignKey, Enum, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


class UserStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class DuplicateDecision(str, enum.Enum):
    same = "same"          # "Ha, bu men yuborgan edim"
    different = "different"  # "Yo'q, bu boshqa hujjat"


# ---------- Foydalanuvchilar (agent/ekspeditorlar) ----------
class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    id_number: Mapped[str] = mapped_column(String(50))  # JSHSHIR
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), default=UserStatus.pending
    )
    approved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="submitted_by_user")


# ---------- Postavshik ----------
class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    inn: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="supplier")


# ---------- Xaridor (do'kon / agentlik) ----------
class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(50), nullable=True)
    client_code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="customer")


# ---------- Sotuvchi agent ("Агент:" maydoni) ----------
class SalesAgent(Base):
    __tablename__ = "sales_agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True)

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="sales_agent")


# ---------- Ekspeditor ("Экспедитор:" maydoni) ----------
class Expediter(Base):
    __tablename__ = "expediters"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True)

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="expediter")


# ---------- Tovarlar katalogi ----------
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Case, PET, va h.k.

    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="product")


# ---------- Hujjat (накладная) ----------
class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    date: Mapped[date_type] = mapped_column(Date, index=True)

    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    sales_agent_id: Mapped[int | None] = mapped_column(ForeignKey("sales_agents.id"), index=True, nullable=True)
    expediter_id: Mapped[int | None] = mapped_column(ForeignKey("expediters.id"), nullable=True)

    submitted_by: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"))

    total_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_sum: Mapped[float] = mapped_column(Numeric(14, 2))
    discount_sum: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    photo_file_id: Mapped[str] = mapped_column(String(300))  # Telegramdagi rasm file_id

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    supplier: Mapped["Supplier"] = relationship(back_populates="invoices")
    customer: Mapped["Customer"] = relationship(back_populates="invoices")
    sales_agent: Mapped["SalesAgent"] = relationship(back_populates="invoices")
    expediter: Mapped["Expediter"] = relationship(back_populates="invoices")
    submitted_by_user: Mapped["TelegramUser"] = relationship(back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))

    quantity: Mapped[float] = mapped_column(Numeric(10, 2))
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2))
    line_total: Mapped[float] = mapped_column(Numeric(14, 2))

    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="items")


# ---------- Bir xil hujjat qayta yuborilganda qaror tarixi ----------
class InvoiceDuplicate(Base):
    __tablename__ = "invoice_duplicates"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    submitted_by: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"))
    decision: Mapped[DuplicateDecision] = mapped_column(Enum(DuplicateDecision))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
