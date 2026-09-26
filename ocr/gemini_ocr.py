import json
import re
import google.generativeai as genai

from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-flash-latest"

# Rasmlarda uchraydigan barcha majburiy maydonlarni qat'iy JSON
# formatida qaytarishni talab qiluvchi ko'rsatma (prompt).
PROMPT = """
Sen tovar-naklad (накладная) hujjatlarini o'qib, faqat quyidagi JSON
sxemasiga mos javob qaytaradigan yordamchisan. Hujjat rus va o'zbek
tillarida, ba'zan qo'lda yozilgan izohlar bilan bo'lishi mumkin.

QOIDALAR:
- Faqat JSON qaytar. Hech qanday izoh, sarlavha yoki ``` belgilarini qo'shma.
- Agar biror maydonni ishonchli o'qiy olmasang, uning qiymatini null qil.
- Sonlarni raqam (number) sifatida qaytar, ichida bo'shliq yoki vergul bo'lmasin
  (masalan "70 308,00" -> 70308.00).
- items ro'yxatida hujjatdagi HAR BIR qatorni alohida element sifatida kiritish shart.
- "Кол-во" ustuni miqdor (quantity), "Цена за ул." narx (unit_price),
  "Всего" qator summasi (line_total).

JSON sxemasi:
{
  "invoice_number": string yoki null,
  "date": "YYYY-MM-DD" yoki null,
  "supplier": {
    "name": string yoki null,
    "inn": string yoki null,
    "address": string yoki null,
    "phone": string yoki null
  },
  "customer": {
    "name": string yoki null,
    "address": string yoki null,
    "inn": string yoki null,
    "client_code": string yoki null
  },
  "sales_agent": string yoki null,
  "expediter": string yoki null,
  "items": [
    {
      "code": string,
      "name": string,
      "unit": string yoki null,
      "quantity": number,
      "unit_price": number,
      "line_total": number
    }
  ],
  "total_qty": number yoki null,
  "total_sum": number,
  "discount_sum": number yoki 0
}
"""


class OCRError(Exception):
    pass


def _extract_json(text: str) -> dict:
    """Model javobidan JSON qismini xavfsiz ajratib oladi."""
    text = text.strip()
    text = re.sub(r"^```json\s*|^```\s*|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise OCRError(f"Model javobini JSON sifatida o'qib bo'lmadi: {e}")


async def recognize_invoice(image_bytes: bytes) -> dict:
    """
    Chek/накладная rasmini Gemini orqali tahlil qilib,
    tuzilgan (structured) ma'lumot qaytaradi.
    """
    model = genai.GenerativeModel(MODEL_NAME)
    image_part = {"mime_type": "image/jpeg", "data": image_bytes}

    response = await model.generate_content_async(
        [PROMPT, image_part],
        generation_config={"temperature": 0, "response_mime_type": "application/json"},
    )

    if not response.text:
        raise OCRError("Model bo'sh javob qaytardi")

    data = _extract_json(response.text)

    required_top = ["invoice_number", "date", "supplier", "customer", "items", "total_sum"]
    missing = [f for f in required_top if f not in data]
    if missing:
        raise OCRError(f"JSON javobda quyidagi maydonlar yo'q: {missing}")

    return data
