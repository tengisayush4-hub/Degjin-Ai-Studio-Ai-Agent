# FB AI Content Agent - Тохиргооны заавар

## Яг юу хийдэг вэ?

Захиалга бичнэ → AI зураг үүснэ → Animated текст давхарлагдаж → MP4 татаж авна

---

## 1. Суулгалт

```bash
pip install -r requirements.txt
```

---

## 2. API Түлхүүр авах

### Gemini API Key
1. https://aistudio.google.com/app/apikey → "Create API Key"

---

## 3. .env файл үүсгэх

```bash
cp .env.example .env
```

`.env` файлд бөглөнө:

```
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxx
PORT=8000
```

---

## 4. Ажиллуулах

```bash
python main.py
```

Дараа нь хөтөч дээр нээнэ: **http://localhost:8000**

---

## Хэрэглэх

Захиалга талбарт ингэж бичнэ:

```
Хонь зарна. 50,000₮. Эрдэнэт хот. 99001122
```

эсвэл:

```
Гоёмсог нялхасын хувцас. Baby Star дэлгүүр. 70,000₮ - 150,000₮. 88001234
```

AI автоматаар:
1. Зургийн тайлбар гаргаж Gemini-д өгнө
2. Зар текст үүсгэнэ (гарчиг, үнэ, холбоо барих, уриалга)
3. Animated MP4 хийнэ
4. Татаж авна → FB page-дээ post хийнэ
