# ФотоРеставратор

Веб-приложение для восстановления и колоризации старых фотографий с помощью ИИ. Работает на компьютере и телефоне.

**Что делает:**
- Убирает царапины, шум и повреждения
- Восстанавливает лица (сохраняя оригинальные черты)
- Делает чёрно-белые фото цветными
- Сохраняет обстановку, здания, природу без изменений

**Бизнес-модель:** 3 фото бесплатно, далее — покупка пакетов через Stripe.

---

## Быстрый старт

### 1. Получите API-ключ Replicate

Зарегистрируйтесь на [replicate.com](https://replicate.com) и скопируйте API-токен. У Replicate есть бесплатный тариф для тестирования.

### 2. Настройте окружение

```bash
cp .env.example .env
# Отредактируйте .env — впишите REPLICATE_API_TOKEN
```

### 3. Запуск через Docker (рекомендуется)

```bash
docker compose up --build
```

Приложение будет доступно на [http://localhost:8000](http://localhost:8000).

### 4. Запуск без Docker (для разработки)

**Бэкенд:**

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Фронтенд:**

```bash
cd frontend
npm install
npm run dev
```

Фронтенд будет на [http://localhost:5173](http://localhost:5173), запросы к API проксируются на порт 8000.

---

## Архитектура

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Frontend    │────▶│  FastAPI Backend  │────▶│  Replicate API   │
│  React+Vite  │◀────│  Python          │◀────│  (AI Models)     │
└──────────────┘     └──────────────────┘     └──────────────────┘
                            │
                     ┌──────┴──────┐
                     │   Stripe    │
                     │  (Платежи)  │
                     └─────────────┘
```

**Пайплайн обработки фото:**

1. **CodeFormer** — восстановление лиц, удаление царапин и шума
2. **DeOldify** — колоризация (модель Artistic для естественных цветов)

## Используемые AI-модели

| Модель | Задача | Почему выбрана |
|--------|--------|----------------|
| [CodeFormer](https://github.com/sczhou/CodeFormer) | Восстановление лиц | Лучше всех сохраняет идентичность лица |
| [DeOldify](https://github.com/jantic/DeOldify) | Колоризация | Исторически точные, естественные цвета |

## Настройка оплаты (Stripe)

1. Создайте аккаунт на [stripe.com](https://stripe.com)
2. В Dashboard создайте Product и Price
3. Впишите ключи в `.env`:
   - `STRIPE_SECRET_KEY` — секретный ключ
   - `STRIPE_PRICE_ID` — ID цены за 1 фото
   - `STRIPE_WEBHOOK_SECRET` — секрет вебхука
4. Настройте Webhook URL: `https://your-domain.com/api/webhook/stripe`

## Структура проекта

```
├── backend/
│   ├── main.py          # FastAPI-сервер, маршруты API
│   ├── restore.py       # Пайплайн восстановления (CodeFormer + DeOldify)
│   ├── payments.py      # Интеграция со Stripe
│   ├── storage.py       # Учёт использования (JSON-файл)
│   ├── config.py        # Конфигурация из .env
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # Главный компонент + сравнение до/после
│   │   ├── main.jsx     # Точка входа React
│   │   └── styles.css   # Стили (адаптивные, мобильные)
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── Dockerfile           # Мультистадийная сборка
├── docker-compose.yml
├── .env.example
└── README.md
```

## Лицензия

MIT
